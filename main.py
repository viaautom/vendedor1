"""
Buscador de Ofertas — orquestrador principal (worker).

Busca ofertas na Shopee e na Amazon para as palavras-chave configuradas
(editáveis pelo painel, via settings.py), persiste tudo no repositório
(storage.ofertas_encontradas) e envia as novas para o canal do Telegram.

Uso:
  python main.py            # roda uma vez e sai
  python main.py --loop     # roda continuamente, respeitando o intervalo
"""
import sys
import time
import logging

from clients import shopee_client, amazon_client
import settings
import storage
import telegram_poster
import whatsapp_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("buscador-ofertas")


def ciclo_de_busca():
    cfg = settings.carregar_configuracoes()
    logger.info("Iniciando ciclo de busca de ofertas...")
    storage.limpar_antigas(dias=30)

    novas_ofertas = []

    for palavra in cfg["keywords"]:
        for cliente, fonte in ((shopee_client, "Shopee"), (amazon_client, "Amazon")):
            try:
                ofertas = cliente.buscar_ofertas(
                    palavra, min_discount_percent=cfg["min_discount_percent"]
                )
            except Exception as e:
                logger.warning(f"Falha ao buscar na {fonte} ('{palavra}'): {e}")
                continue

            for oferta in ofertas:
                oferta["keyword"] = palavra
            ofertas = settings.filtrar_por_preco(ofertas, cfg)

            for oferta in ofertas:
                storage.registrar_oferta(oferta)
            novas_ofertas.extend(ofertas)

            ids_vistos = {oferta["id"] for oferta in ofertas}
            storage.marcar_indisponiveis(palavra, fonte, ids_vistos)

    postadas = 0
    for oferta in novas_ofertas:
        if storage.ja_foi_postada(oferta["id"]):
            continue

        sucesso = telegram_poster.postar_oferta(oferta)
        if sucesso:
            storage.marcar_como_postada(oferta["id"], oferta["fonte"])
            storage.marcar_enviado(oferta["id"], "telegram")
            postadas += 1
            time.sleep(2)  # evita rajada de mensagens muito rápida

    logger.info(f"Ciclo concluído. {postadas} nova(s) oferta(s) postada(s) no Telegram.")

    grupos = storage.grupos_ativos()
    if grupos:
        if not whatsapp_client.status().get("connected"):
            logger.warning("whatsapp-service não está conectado — pulando envio aos grupos.")
        else:
            enviadas_grupo = 0
            for oferta in novas_ofertas:
                if storage.foi_enviada(oferta["id"], "whatsapp_grupo"):
                    continue
                texto = whatsapp_client.formatar_mensagem(oferta)
                sucesso_algum = False
                for grupo in grupos:
                    if whatsapp_client.enviar_mensagem(grupo["jid"], texto):
                        sucesso_algum = True
                if sucesso_algum:
                    storage.marcar_enviado(oferta["id"], "whatsapp_grupo")
                    enviadas_grupo += 1
            logger.info(f"{enviadas_grupo} oferta(s) enviada(s) aos grupos de WhatsApp.")

    return cfg["check_interval_hours"]


def main():
    if "--loop" in sys.argv:
        logger.info("Modo contínuo ativado.")
        while True:
            intervalo = ciclo_de_busca()
            logger.info(f"Próximo ciclo em {intervalo}h.")
            time.sleep(intervalo * 3600)
    else:
        ciclo_de_busca()


if __name__ == "__main__":
    main()
