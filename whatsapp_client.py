"""
Cliente HTTP fino para o whatsapp-service (Node.js/Baileys) — mesmo
espírito do telegram_poster.py, mas para grupos de WhatsApp.
"""
import requests

from config import WHATSAPP_SERVICE_URL, WHATSAPP_SERVICE_TOKEN

_HEADERS = {"X-Internal-Token": WHATSAPP_SERVICE_TOKEN} if WHATSAPP_SERVICE_TOKEN else {}


def status() -> dict:
    """Retorna {'connected': bool}. Em caso de falha de rede, considera
    desconectado em vez de propagar a exceção (serviço pode estar subindo)."""
    try:
        resp = requests.get(f"{WHATSAPP_SERVICE_URL}/status", headers=_HEADERS, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {"connected": False}


def qr_disponivel() -> bytes | None:
    try:
        resp = requests.get(f"{WHATSAPP_SERVICE_URL}/qr", headers=_HEADERS, timeout=5)
        if resp.status_code == 200:
            return resp.content
        return None
    except requests.RequestException:
        return None


def listar_grupos() -> list[dict]:
    try:
        resp = requests.get(f"{WHATSAPP_SERVICE_URL}/groups", headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return []


def enviar_mensagem(jid: str, mensagem: str) -> bool:
    try:
        resp = requests.post(
            f"{WHATSAPP_SERVICE_URL}/send",
            json={"jid": jid, "message": mensagem},
            headers=_HEADERS,
            timeout=30,
        )
        return resp.ok and resp.json().get("ok", False)
    except requests.RequestException:
        return False


def formatar_mensagem(oferta: dict) -> str:
    return (
        f"🔥 *{oferta.get('nome', 'Oferta')}*\n\n"
        f"💰 Preço: R$ {float(oferta.get('preco', 0) or 0):.2f}\n"
        f"📉 Desconto: {oferta.get('desconto_percent', 0)}%\n"
        f"🛒 Loja: {oferta.get('fonte', 'Loja')}\n\n"
        f"👉 {oferta.get('link_afiliado', '')}"
    )
