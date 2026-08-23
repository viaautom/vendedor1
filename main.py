"""
Buscador de Ofertas — orquestrador principal.

Roda periodicamente (a cada CHECK_INTERVAL_HOURS), busca ofertas na
Shopee e na Amazon para as palavras-chave configuradas, filtra as que
já foram postadas e envia as novas para o canal do Telegram.

Uso:
  python main.py            # roda uma vez e sai
  python main.py --loop     # roda continuamente, respeitando o intervalo
"""
import sys
import time
import logging

import schedule

from config import KEYWORDS, CHECK_INTERVAL_HOURS
from clients import shopee_client, amazon_client
import storage
import telegram_poster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("buscador-ofertas")


def ciclo_de_busca():
    logger.info("Iniciando ciclo de busca de ofertas...")
    storage.limpar_antigas(dias=30)

    novas_ofertas = []

    for palavra in KEYWORDS:
        # --- Shopee ---
        try:
            ofertas_shopee = shopee_client.buscar_ofertas(palavra)
            novas_ofertas.extend(ofertas_shopee)
        except Exception as e:
            logger.warning(f"Falha ao buscar na Shopee ('{palavra}'): {e}")

        # --- Amazon ---
        try:
            ofertas_amazon = amazon_client.buscar_ofertas(palavra)
            novas_ofertas.extend(ofertas_amazon)
        except Exception as e:
            logger.warning(f"Falha ao buscar na Amazon ('{palavra}'): {e}")

    postadas = 0
    for oferta in novas_ofertas:
        if storage.ja_foi_postada(oferta["id"]):
            continue

        sucesso = telegram_poster.postar_oferta(oferta)
        if sucesso:
            storage.marcar_como_postada(oferta["id"], oferta["fonte"])
            postadas += 1
            time.sleep(2)  # evita rajada de mensagens muito rápida

    logger.info(f"Ciclo concluído. {postadas} nova(s) oferta(s) postada(s).")


def main():
    if "--loop" in sys.argv:
        logger.info(
            f"Modo contínuo ativado. Verificando a cada {CHECK_INTERVAL_HOURS}h."
        )
        ciclo_de_busca()  # roda uma vez imediatamente
        schedule.every(CHECK_INTERVAL_HOURS).hours.do(ciclo_de_busca)
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        ciclo_de_busca()


if __name__ == "__main__":
    main()
