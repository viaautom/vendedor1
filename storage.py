"""
Controle simples de deduplicação: guarda o ID de cada oferta já postada
para não repetir a mesma promoção em execuções seguintes.
"""
import sqlite3
from datetime import datetime, timedelta

from config import DATABASE_PATH


def _connect():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ofertas_postadas (
            id TEXT PRIMARY KEY,
            fonte TEXT,
            postado_em TEXT
        )
        """
    )
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
