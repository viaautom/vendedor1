"""
Persistência do sistema: deduplicação de posts, repositório de ofertas
encontradas, configurações editáveis pelo painel e links da linktree.
"""
import sqlite3
from datetime import datetime, timedelta

from config import DATABASE_PATH


def _connect():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ofertas_postadas (
            id TEXT PRIMARY KEY,
            fonte TEXT,
            postado_em TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ofertas_encontradas (
            id TEXT PRIMARY KEY,
            fonte TEXT,
            keyword TEXT,
            nome TEXT,
            preco REAL,
            desconto_percent INTEGER,
            link_afiliado TEXT,
            imagem_url TEXT,
            primeira_vez_em TEXT,
            ultima_vez_em TEXT,
            enviado_telegram INTEGER DEFAULT 0,
            enviado_whatsapp INTEGER DEFAULT 0,
            disponivel INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS linktree_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT,
            url TEXT,
            emoji TEXT,
            ordem INTEGER DEFAULT 0,
            ativo INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_grupos (
            jid TEXT PRIMARY KEY,
            nome TEXT,
            ativo INTEGER DEFAULT 0
        )
        """
    )
    try:
        conn.execute("ALTER TABLE ofertas_encontradas ADD COLUMN enviado_whatsapp_grupo INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # coluna já existe (banco criado antes desta versão)
    return conn


def ja_foi_postada(oferta_id: str) -> bool:
    conn = _connect()
    cur = conn.execute(
        "SELECT 1 FROM ofertas_postadas WHERE id = ?", (oferta_id,)
    )
    resultado = cur.fetchone() is not None
    conn.close()
    return resultado


def marcar_como_postada(oferta_id: str, fonte: str):
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO ofertas_postadas (id, fonte, postado_em) VALUES (?, ?, ?)",
        (oferta_id, fonte, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def limpar_antigas(dias: int = 30):
    """Remove registros com mais de X dias, permitindo repostar a oferta
    se ela voltar a ficar em promoção depois de muito tempo."""
    limite = (datetime.utcnow() - timedelta(days=dias)).isoformat()
    conn = _connect()
    conn.execute("DELETE FROM ofertas_postadas WHERE postado_em < ?", (limite,))
    conn.commit()
    conn.close()


# --- Repositório de ofertas encontradas -----------------------------------

def registrar_oferta(oferta: dict):
    """Insere a oferta se for nova, ou atualiza preço/desconto/última vez
    vista se já existia — preserva primeira_vez_em e os flags de envio."""
    agora = datetime.utcnow().isoformat()
    conn = _connect()
    existe = conn.execute(
        "SELECT primeira_vez_em FROM ofertas_encontradas WHERE id = ?",
        (oferta["id"],),
    ).fetchone()

    if existe:
        conn.execute(
            """
            UPDATE ofertas_encontradas
            SET fonte = ?, keyword = ?, nome = ?, preco = ?,
                desconto_percent = ?, link_afiliado = ?, imagem_url = ?,
                ultima_vez_em = ?, disponivel = 1
            WHERE id = ?
            """,
            (
                oferta.get("fonte", ""),
                oferta.get("keyword", ""),
                oferta.get("nome", ""),
                oferta.get("preco", 0),
                oferta.get("desconto_percent", 0),
                oferta.get("link_afiliado", ""),
                oferta.get("imagem_url", ""),
                agora,
                oferta["id"],
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO ofertas_encontradas
                (id, fonte, keyword, nome, preco, desconto_percent,
                 link_afiliado, imagem_url, primeira_vez_em, ultima_vez_em,
                 enviado_telegram, enviado_whatsapp, disponivel)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            (
                oferta["id"],
                oferta.get("fonte", ""),
                oferta.get("keyword", ""),
                oferta.get("nome", ""),
                oferta.get("preco", 0),
                oferta.get("desconto_percent", 0),
                oferta.get("link_afiliado", ""),
                oferta.get("imagem_url", ""),
                agora,
                agora,
            ),
        )
    conn.commit()
    conn.close()


def marcar_indisponiveis(keyword: str, fonte: str, ids_vistos: set):
    """Marca disponivel=0 para ofertas dessa keyword+fonte que não
    apareceram na busca mais recente (ciclo que respondeu com sucesso)."""
    conn = _connect()
    linhas = conn.execute(
        "SELECT id FROM ofertas_encontradas WHERE keyword = ? AND fonte = ? AND disponivel = 1",
        (keyword, fonte),
    ).fetchall()
    sumidos = [row[0] for row in linhas if row[0] not in ids_vistos]
    if sumidos:
        conn.executemany(
            "UPDATE ofertas_encontradas SET disponivel = 0 WHERE id = ?",
            [(id_,) for id_ in sumidos],
        )
        conn.commit()
    conn.close()


def listar_ofertas(somente_disponiveis: bool = False) -> list[dict]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM ofertas_encontradas"
    if somente_disponiveis:
        query += " WHERE disponivel = 1"
    query += " ORDER BY ultima_vez_em DESC"
    linhas = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in linhas]


_COLUNAS_ENVIO = {
    "telegram": "enviado_telegram",
    "whatsapp": "enviado_whatsapp",
    "whatsapp_grupo": "enviado_whatsapp_grupo",
}


def foi_enviada(oferta_id: str, canal: str) -> bool:
    coluna = _COLUNAS_ENVIO.get(canal, "enviado_whatsapp")
    conn = _connect()
    linha = conn.execute(
        f"SELECT {coluna} FROM ofertas_encontradas WHERE id = ?", (oferta_id,)
    ).fetchone()
    conn.close()
    return bool(linha and linha[0])


def marcar_enviado(oferta_id: str, canal: str):
    coluna = _COLUNAS_ENVIO.get(canal, "enviado_whatsapp")
    conn = _connect()
    conn.execute(
        f"UPDATE ofertas_encontradas SET {coluna} = 1 WHERE id = ?",
        (oferta_id,),
    )
    conn.commit()
    conn.close()


# --- Configurações (chave-valor) -------------------------------------------

def obter_config_kv() -> dict:
    conn = _connect()
    linhas = conn.execute("SELECT chave, valor FROM configuracoes").fetchall()
    conn.close()
    return {chave: valor for chave, valor in linhas}


def definir_config_kv(valores: dict):
    conn = _connect()
    conn.executemany(
        "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)",
        list(valores.items()),
    )
    conn.commit()
    conn.close()


# --- Linktree ----------------------------------------------------------

def listar_links(somente_ativos: bool = False) -> list[dict]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM linktree_links"
    if somente_ativos:
        query += " WHERE ativo = 1"
    query += " ORDER BY ordem ASC, id ASC"
    linhas = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in linhas]


def salvar_links(links: list[dict]):
    """Substitui a lista inteira de links (mais simples que fazer diff,
    dado que vem de um formulário único no painel)."""
    conn = _connect()
    conn.execute("DELETE FROM linktree_links")
    conn.executemany(
        """
        INSERT INTO linktree_links (label, url, emoji, ordem, ativo)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                link.get("label", ""),
                link.get("url", ""),
                link.get("emoji", "🔗"),
                idx,
                1 if link.get("ativo", True) else 0,
            )
            for idx, link in enumerate(links)
        ],
    )
    conn.commit()
    conn.close()


# --- Grupos de WhatsApp --------------------------------------------------

def listar_grupos_salvos() -> list[dict]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    linhas = conn.execute("SELECT * FROM whatsapp_grupos ORDER BY nome ASC").fetchall()
    conn.close()
    return [dict(row) for row in linhas]


def grupos_ativos() -> list[dict]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    linhas = conn.execute("SELECT * FROM whatsapp_grupos WHERE ativo = 1").fetchall()
    conn.close()
    return [dict(row) for row in linhas]


def salvar_grupos(grupos: list[dict]):
    """Substitui a lista inteira de grupos conhecidos (vem de
    whatsapp_client.listar_grupos() + seleção do admin no formulário)."""
    conn = _connect()
    conn.execute("DELETE FROM whatsapp_grupos")
    conn.executemany(
        "INSERT INTO whatsapp_grupos (jid, nome, ativo) VALUES (?, ?, ?)",
        [
            (grupo["jid"], grupo.get("nome", grupo.get("name", "")), 1 if grupo.get("ativo") else 0)
            for grupo in grupos
        ],
    )
    conn.commit()
    conn.close()
