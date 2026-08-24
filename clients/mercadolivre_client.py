import requests

from config import MIN_DISCOUNT_PERCENT
from storage import gerar_id_curto


def _parse_price(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(".", "").replace(",", "."))
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in ("value", "amount", "price", "total_amount"):
            if key in value:
                return _parse_price(value[key])
        return None
    return None


def buscar_ofertas(keyword: str, limite: int = 10, min_discount_percent: int = None) -> list[dict]:
    limite_desconto = MIN_DISCOUNT_PERCENT if min_discount_percent is None else min_discount_percent
    url = "https://api.mercadolibre.com/sites/MLB/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Accept": "application/json",
    }
    params = {"q": keyword, "limit": limite}

    resp = requests.get(url, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    dados = resp.json()

    ofertas = []
    for item in dados.get("results", [])[:limite]:
        preco_atual = _parse_price(item.get("price"))
        preco_original = _parse_price(item.get("original_price")) or _parse_price(item.get("base_price"))
        if preco_atual is None or preco_original in (None, 0):
            continue

        desconto_percent = round((1 - (preco_atual / preco_original)) * 100)
        if desconto_percent < limite_desconto:
            continue

        nome = item.get("title", "")
        link = item.get("permalink", "")
        ofertas.append(
            {
                "id": gerar_id_curto(nome, link, "ML"),
                "fonte": "Mercado Livre",
                "nome": nome,
                "preco": preco_atual,
                "desconto_percent": desconto_percent,
                "link_afiliado": link,
                "imagem_url": item.get("thumbnail", ""),
            }
        )

    return ofertas
