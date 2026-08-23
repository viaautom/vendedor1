"""
Configuração central do buscador de ofertas.
Todas as credenciais vêm de variáveis de ambiente (.env) — nunca deixe
chaves de API hardcoded no código.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")  # ex: "@seucanal" ou "-1001234567890"

# --- Shopee Affiliate Open API ---
SHOPEE_PARTNER_ID = os.getenv("SHOPEE_PARTNER_ID", "")
SHOPEE_PARTNER_KEY = os.getenv("SHOPEE_PARTNER_KEY", "")

# --- Amazon PA API (via biblioteca python-amazon-paapi) ---
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY", "")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY", "")
AMAZON_PARTNER_TAG = os.getenv("AMAZON_PARTNER_TAG", "")
AMAZON_COUNTRY = os.getenv("AMAZON_COUNTRY", "BR")

# --- Regras de filtro das ofertas ---
MIN_DISCOUNT_PERCENT = int(os.getenv("MIN_DISCOUNT_PERCENT", "30"))
MIN_PRICE = float(os.getenv("MIN_PRICE", "0"))
MAX_PRICE = float(os.getenv("MAX_PRICE", "1000"))

# Palavras-chave do nicho (fitness / bem-estar) — usadas na busca por produto
KEYWORDS = [
    "whey protein",
    "roupa fitness",
    "tapete de yoga",
    "garrafa térmica academia",
    "faixa elástica exercício",
    "creatina",
    "massageador muscular",
]

# --- Execução ---
CHECK_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "6"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "ofertas.db")

# --- Painel administrativo ---
# Senha de acesso ao dashboard.py. Se ficar vazia, o painel fica aberto sem
# senha — só deixe vazio em teste local. Sempre defina uma senha forte antes
# de publicar o painel na internet.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
