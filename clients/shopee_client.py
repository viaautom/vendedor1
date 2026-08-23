"""
Cliente para a Shopee Affiliate Open API (GraphQL).

IMPORTANTE: a Shopee atualiza a documentação e o esquema de assinatura
com alguma frequência. Antes de rodar em produção, confira o endpoint,
os campos da query e o método de assinatura no painel oficial de
afiliados da Shopee (Portal do Afiliado > API). O código abaixo segue
o padrão de autenticação usual (App ID + timestamp + payload + secret,
com hash SHA256), mas trate como ponto de partida, não como garantia
de funcionamento sem ajustes.
"""
import hashlib
import time
import requests

from config import SHOPEE_PARTNER_ID, SHOPEE_PARTNER_KEY, MIN_DISCOUNT_PERCENT

GRAPHQL_ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"


def _assinar_payload(payload: str, timestamp: int) -> str:
    base = f"{SHOPEE_PARTNER_ID}{timestamp}{payload}{SHOPEE_PARTNER_KEY}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _montar_headers(payload: str) -> dict:
    timestamp = int(time.time())
    assinatura = _assinar_payload(payload, timestamp)
    return {
        "Content-Type": "application/json",
        "Authorization": (
            f"SHA256 Credential={SHOPEE_PARTNER_ID}, "
            f"Signature={assinatura}, Timestamp={timestamp}"
        ),
    }


def buscar_ofertas(keyword: str, limite: int = 20, min_discount_percent: int = None) -> list[dict]:
    """
    Busca produtos por palavra-chave e retorna apenas os que atendem
    ao desconto mínimo configurado.
    Retorna uma lista de dicts: id, nome, preco, preco_original,
    desconto_percent, link_afiliado, imagem_url.
    """
    limite_desconto = MIN_DISCOUNT_PERCENT if min_discount_percent is None else min_discount_percent
    query = """
    query($keyword: String!, $limit: Int!) {
      productOfferV2(keyword: $keyword, limit: $limit) {
        nodes {
          itemId
          productName
          price
          priceMin
          priceMax
          offerLink
          imageUrl
          priceDiscountRate
        }
      }
    }
    """
    payload_dict = {
        "query": query,
        "variables": {"keyword": keyword, "limit": limite},
    }
    import json

    payload = json.dumps(payload_dict)
    headers = _montar_headers(payload)

    resp = requests.post(GRAPHQL_ENDPOINT, data=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    dados = resp.json()

    nodes = (
        dados.get("data", {})
        .get("productOfferV2", {})
        .get("nodes", [])
    )

    ofertas = []
    for item in nodes:
        desconto = item.get("priceDiscountRate", 0)
        if desconto is None or desconto < limite_desconto:
            continue
        ofertas.append(
            {
                "id": f"shopee_{item['itemId']}",
                "fonte": "Shopee",
                "nome": item.get("productName", ""),
                "preco": item.get("price"),
                "desconto_percent": desconto,
                "link_afiliado": item.get("offerLink", ""),
                "imagem_url": item.get("imageUrl", ""),
            }
        )
    return ofertas
