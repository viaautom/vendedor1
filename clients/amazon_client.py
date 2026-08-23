"""
Cliente para a Amazon Product Advertising API (PA API 5.0), usando a
biblioteca de terceiros `python-amazon-paapi`, que simplifica bastante
a assinatura das requisições.

Requisitos:
  pip install python-amazon-paapi

Lembrete: a Amazon exige que sua conta de Associados tenha vendas
qualificadas recentes para manter o acesso à API ativo — se ficar
muito tempo sem vender, as credenciais podem parar de funcionar.
"""
from amazon_paapi import AmazonApi

from config import (
    AMAZON_ACCESS_KEY,
    AMAZON_SECRET_KEY,
    AMAZON_PARTNER_TAG,
    AMAZON_COUNTRY,
    MIN_DISCOUNT_PERCENT,
)

_api = None


def _get_api() -> AmazonApi:
    global _api
    if _api is None:
        _api = AmazonApi(
            AMAZON_ACCESS_KEY,
            AMAZON_SECRET_KEY,
            AMAZON_PARTNER_TAG,
            AMAZON_COUNTRY,
        )
    return _api


def buscar_ofertas(keyword: str, limite: int = 10, min_discount_percent: int = None) -> list[dict]:
    """
    Busca produtos por palavra-chave na Amazon e retorna apenas os que
    têm desconto igual ou acima do mínimo configurado.
    """
    limite_desconto = MIN_DISCOUNT_PERCENT if min_discount_percent is None else min_discount_percent
    api = _get_api()
    resultados = api.search_items(keywords=keyword, item_count=limite)

    ofertas = []
    if not resultados or not getattr(resultados, "items", None):
        return ofertas

    for item in resultados.items:
        try:
            preco_atual = item.offers.listings[0].price.amount
            preco_original = getattr(
                item.offers.listings[0].saving_basis, "amount", None
            )
        except (AttributeError, IndexError, TypeError):
            continue

        if not preco_original or preco_original <= 0:
            continue

        desconto_percent = round((1 - (preco_atual / preco_original)) * 100)
        if desconto_percent < limite_desconto:
            continue

        ofertas.append(
            {
                "id": f"amazon_{item.asin}",
                "fonte": "Amazon",
                "nome": item.item_info.title.display_value,
                "preco": preco_atual,
                "desconto_percent": desconto_percent,
                "link_afiliado": item.detail_page_url,
                "imagem_url": getattr(
                    getattr(item.images.primary, "large", None), "url", ""
                ),
            }
        )
    return ofertas
