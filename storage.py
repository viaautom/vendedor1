"""
Persistência do sistema: deduplicação de posts, repositório de ofertas
encontradas, configurações editáveis pelo painel e links da linktree.
"""
import hashlib
import re
import sqlite3
from datetime import datetime, timedelta

from config import DATABASE_PATH


_PADRAO_ID_PRODUTO = re.compile(r"^[A-Z]{3}\d{3}$")
_TOTAL_IDS_PRODUTOS = 26**3 * 1000


def _candidato_id(chave: str, usados: set[str]) -> str:
    inicio = int.from_bytes(
        hashlib.sha256(chave.encode("utf-8")).digest()[:4], "big"
    ) % _TOTAL_IDS_PRODUTOS
    for deslocamento in range(_TOTAL_IDS_PRODUTOS):
        numero = (inicio + deslocamento) % _TOTAL_IDS_PRODUTOS
        letras_numero, digitos = divmod(numero, 1000)
        letras = ""
        for _ in range(3):
            letras = chr(65 + letras_numero % 26) + letras
            letras_numero //= 26
        candidato = f"{letras}{digitos:03d}"
        if candidato not in usados:
            return candidato
    raise RuntimeError("Limite de 17.576.000 IDs de produtos atingido.")


def gerar_id_curto(nome: str, link: str = "", prefix: str = "P") -> str:
    """Reserva um ID no formato AAA000, sem usar o nome no resultado.

    A reserva fica no SQLite para que o mesmo ID nunca seja entregue a dois
    produtos, inclusive quando dois cadastros acontecem quase ao mesmo tempo.
    """
    chave = (link or nome or "produto").strip()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existente = conn.execute(
            "SELECT id FROM ids_produtos WHERE chave = ?", (chave,)
        ).fetchone()
        if existente and _PADRAO_ID_PRODUTO.fullmatch(existente[0]):
            return existente[0]

        usados = {row[0] for row in conn.execute("SELECT id FROM ids_produtos")}
        for _ in range(_TOTAL_IDS_PRODUTOS):
            candidato = _candidato_id(chave, usados)
            try:
                if existente:
                    id_antigo = existente[0]
                    conn.execute(
                        "UPDATE ids_produtos SET id = ? WHERE chave = ?",
                        (candidato, chave),
                    )
                    for tabela in ("ofertas_encontradas", "ofertas_postadas", "envios_log"):
                        conn.execute(
                            f"UPDATE {tabela} SET id = ? WHERE id = ?"
                            if tabela != "envios_log"
                            else "UPDATE envios_log SET oferta_id = ? WHERE oferta_id = ?",
                            (candidato, id_antigo),
                        )
                else:
                    conn.execute(
                        "INSERT INTO ids_produtos (id, chave) VALUES (?, ?)",
                        (candidato, chave),
                    )
                conn.commit()
                return candidato
            except sqlite3.IntegrityError:
                usados.add(candidato)
        raise RuntimeError("Limite de 17.576.000 IDs de produtos atingido.")
    finally:
        conn.close()


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
        CREATE TABLE IF NOT EXISTS ids_produtos (
            id TEXT PRIMARY KEY,
            chave TEXT UNIQUE NOT NULL
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS loja_banners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imagem_url TEXT,
            link_url TEXT,
            ordem INTEGER DEFAULT 0,
            ativo INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            whatsapp TEXT,
            origem TEXT,
            consentimento INTEGER DEFAULT 0,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS acessos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pagina TEXT NOT NULL,
            acessado_em TEXT NOT NULL
        )
        """
    )
    try:
        conn.execute("ALTER TABLE ofertas_encontradas ADD COLUMN enviado_whatsapp_grupo INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # coluna já existe (banco criado antes desta versão)
    try:
        conn.execute("ALTER TABLE ofertas_encontradas ADD COLUMN destaque INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS envios_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oferta_id TEXT,
            canal TEXT,
            enviado_em TEXT
        )
        """
    )
    _migrar_ids_legados(conn)
    return conn


def _migrar_ids_legados(conn):
    """Converte IDs antigos e suas referências para o formato AAA000."""
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    linhas = conn.execute(
        "SELECT id, chave FROM ids_produtos ORDER BY rowid"
    ).fetchall()
    usados = {
        row[0]
        for row in linhas
        if _PADRAO_ID_PRODUTO.fullmatch(row[0])
    }
    try:
        for id_antigo, chave in linhas:
            if _PADRAO_ID_PRODUTO.fullmatch(id_antigo):
                continue
            novo_id = _candidato_id(chave, usados)
            conn.execute(
                "UPDATE ids_produtos SET id = ? WHERE id = ?",
                (novo_id, id_antigo),
            )
            conn.execute(
                "UPDATE ofertas_encontradas SET id = ? WHERE id = ?",
                (novo_id, id_antigo),
            )
            conn.execute(
                "UPDATE ofertas_postadas SET id = ? WHERE id = ?",
                (novo_id, id_antigo),
            )
            conn.execute(
                "UPDATE envios_log SET oferta_id = ? WHERE oferta_id = ?",
                (novo_id, id_antigo),
            )
            usados.add(novo_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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


def remover_oferta(oferta_id: str):
    conn = _connect()
    conn.execute("DELETE FROM ofertas_encontradas WHERE id = ?", (oferta_id,))
    conn.commit()
    conn.close()


_COLUNAS_EDITAVEIS = {"nome", "preco", "desconto_percent", "keyword", "imagem_url", "link_afiliado", "destaque"}


def atualizar_oferta(oferta_id: str, campos: dict):
    """Atualiza manualmente um subconjunto de colunas (edição pelo painel).
    Ignora chaves fora de _COLUNAS_EDITAVEIS por segurança."""
    campos = {chave: valor for chave, valor in campos.items() if chave in _COLUNAS_EDITAVEIS}
    if not campos:
        return
    atribuicoes = ", ".join(f"{chave} = ?" for chave in campos)
    conn = _connect()
    conn.execute(
        f"UPDATE ofertas_encontradas SET {atribuicoes} WHERE id = ?",
        (*campos.values(), oferta_id),
    )
    conn.commit()
    conn.close()


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
    conn.execute(
        "INSERT INTO envios_log (oferta_id, canal, enviado_em) VALUES (?, ?, ?)",
        (oferta_id, canal, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


# --- Estatísticas ---------------------------------------------------------

def contagem_por_nicho(somente_disponiveis: bool = False) -> list[dict]:
    conn = _connect()
    query = "SELECT keyword, COUNT(*) AS total FROM ofertas_encontradas"
    if somente_disponiveis:
        query += " WHERE disponivel = 1"
    query += " GROUP BY keyword ORDER BY total DESC"
    linhas = conn.execute(query).fetchall()
    conn.close()
    return [{"keyword": keyword or "Outros", "total": total} for keyword, total in linhas]


def contagem_nao_enviados() -> int:
    """Ofertas que ainda não saíram por nenhum canal (Telegram, WhatsApp
    pessoal ou grupo)."""
    conn = _connect()
    total = conn.execute(
        """
        SELECT COUNT(*) FROM ofertas_encontradas
        WHERE enviado_telegram = 0 AND enviado_whatsapp = 0 AND enviado_whatsapp_grupo = 0
        """
    ).fetchone()[0]
    conn.close()
    return total


def contagem_enviados_hoje() -> dict:
    """{'telegram': N, 'whatsapp': N, 'whatsapp_grupo': N} — envios cujo
    enviado_em cai no dia de hoje (UTC)."""
    hoje = datetime.utcnow().strftime("%Y-%m-%d")
    conn = _connect()
    linhas = conn.execute(
        "SELECT canal, COUNT(*) FROM envios_log WHERE substr(enviado_em, 1, 10) = ? GROUP BY canal",
        (hoje,),
    ).fetchall()
    conn.close()
    contagem = {"telegram": 0, "whatsapp": 0, "whatsapp_grupo": 0}
    for canal, total in linhas:
        contagem[canal] = total
    return contagem


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


# --- Vitrine (loja.py) ---------------------------------------------------

def listar_banners(somente_ativos: bool = False) -> list[dict]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM loja_banners"
    if somente_ativos:
        query += " WHERE ativo = 1"
    query += " ORDER BY ordem ASC, id ASC"
    linhas = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in linhas]


def salvar_banners(banners: list[dict]):
    """Substitui a lista inteira de banners (mesmo padrão de salvar_links)."""
    conn = _connect()
    conn.execute("DELETE FROM loja_banners")
    conn.executemany(
        """
        INSERT INTO loja_banners (imagem_url, link_url, ordem, ativo)
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                banner.get("imagem_url", ""),
                banner.get("link_url", ""),
                idx,
                1 if banner.get("ativo", True) else 0,
            )
            for idx, banner in enumerate(banners)
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


# --- Leads e acessos -------------------------------------------------------

def registrar_acesso(pagina: str):
    conn = _connect()
    conn.execute(
        "INSERT INTO acessos (pagina, acessado_em) VALUES (?, ?)",
        (pagina, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def salvar_lead(nome: str, email: str, whatsapp: str, origem: str) -> bool:
    """Salva um lead novo e retorna False quando o e-mail já existe."""
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO leads (nome, email, whatsapp, origem, consentimento, criado_em)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (nome.strip(), email.strip().lower(), whatsapp.strip(), origem, datetime.utcnow().isoformat()),
        )
    except sqlite3.IntegrityError:
        conn.close()
        return False
    conn.commit()
    conn.close()
    return True


def resumo_leads_acessos() -> dict:
    conn = _connect()
    hoje = datetime.utcnow().strftime("%Y-%m-%d")
    resumo = {
        "total_leads": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
        "total_acessos": conn.execute("SELECT COUNT(*) FROM acessos").fetchone()[0],
        "leads_hoje": conn.execute("SELECT COUNT(*) FROM leads WHERE substr(criado_em, 1, 10) = ?", (hoje,)).fetchone()[0],
        "acessos_hoje": conn.execute("SELECT COUNT(*) FROM acessos WHERE substr(acessado_em, 1, 10) = ?", (hoje,)).fetchone()[0],
    }
    conn.close()
    return resumo


def acessos_por_dia(dias: int = 14) -> list[dict]:
    limite = (datetime.utcnow() - timedelta(days=dias - 1)).strftime("%Y-%m-%d")
    conn = _connect()
    linhas = conn.execute(
        """
        SELECT substr(acessado_em, 1, 10) AS dia, pagina, COUNT(*) AS total
        FROM acessos WHERE substr(acessado_em, 1, 10) >= ?
        GROUP BY dia, pagina ORDER BY dia ASC
        """,
        (limite,),
    ).fetchall()
    conn.close()
    return [{"dia": dia, "pagina": pagina, "total": total} for dia, pagina, total in linhas]


def listar_leads() -> list[dict]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    linhas = conn.execute("SELECT * FROM leads ORDER BY criado_em DESC").fetchall()
    conn.close()
    return [dict(linha) for linha in linhas]
