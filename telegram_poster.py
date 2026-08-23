"""
Posta ofertas no canal do Telegram usando a API oficial de Bots.
Para configurar:
  1. Fale com @BotFather no Telegram, crie um bot e pegue o token.
  2. Adicione o bot como administrador do seu canal.
  3. Pegue o ID/username do canal (ex: @seucanal ou -1001234567890).
"""
import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def formatar_mensagem(oferta: dict) -> str:
    return (
        f"🔥 *{oferta['nome']}*\n\n"
        f"💰 Preço: R$ {oferta['preco']:.2f}\n"
        f"📉 Desconto: {oferta['desconto_percent']}%\n"
        f"🛒 Loja: {oferta['fonte']}\n\n"
        f"👉 [Ver oferta]({oferta['link_afiliado']})"
    )


def postar_oferta(oferta: dict) -> bool:
    texto = formatar_mensagem(oferta)
    imagem = oferta.get("imagem_url")

    if imagem:
        url = f"{API_BASE}/sendPhoto"
        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "photo": imagem,
            "caption": texto,
            "parse_mode": "Markdown",
        }
    else:
        url = f"{API_BASE}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": texto,
            "parse_mode": "Markdown",
        }

    resp = requests.post(url, data=payload, timeout=15)
    if not resp.ok:
        print(f"[ERRO] Falha ao postar no Telegram: {resp.status_code} {resp.text}")
        return False
    return True
