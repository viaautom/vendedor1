"""
Extrai nome, preço e imagem de uma página de produto a partir do link —
usado no cadastro manual de ofertas pra pré-preencher o formulário. Lê os
metadados que a maioria das lojas já publica pra compartilhamento social
(JSON-LD schema.org/Product e meta tags Open Graph), sem precisar de um
scraper específico por site. Cobertura varia: sites que renderizam tudo
via JavaScript (sem dados no HTML inicial) podem não retornar nada — os
campos ficam em branco e o usuário preenche à mão.
"""
import json
import re

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def _parse_preco(valor) -> float | None:
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        limpo = re.sub(r"[^\d,.]", "", valor).strip()
        if not limpo:
            return None
        if "," in limpo and "." in limpo:
            limpo = limpo.replace(".", "").replace(",", ".")
        elif "," in limpo:
            limpo = limpo.replace(",", ".")
        try:
            return float(limpo)
        except ValueError:
            return None
    return None


def _calcular_desconto(preco_atual: float | None, preco_original: float | None) -> int:
    if preco_atual is None or preco_original is None:
        return 0
    if preco_original <= 0 or preco_atual <= 0:
        return 0
    if preco_original <= preco_atual:
        return 0
    percentual = round((1 - (preco_atual / preco_original)) * 100)
    return max(0, min(100, percentual))


def _de_json_ld(soup: BeautifulSoup) -> dict:
    dados = {"nome": "", "preco": None, "imagem_url": "", "desconto_percent": 0}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            bloco = json.loads(script.string or "")
        except (ValueError, TypeError):
            continue
        candidatos = bloco if isinstance(bloco, list) else [bloco]
        for item in candidatos:
            if not isinstance(item, dict) or item.get("@type") != "Product":
                continue
            if not dados.get("nome") and item.get("name"):
                dados["nome"] = item["name"]
            imagem = item.get("image")
            if isinstance(imagem, list):
                imagem = imagem[0] if imagem else None
            if not dados.get("imagem_url") and imagem:
                dados["imagem_url"] = imagem

            ofertas = item.get("offers")
            if isinstance(ofertas, list):
                ofertas = ofertas[0] if ofertas else {}
            if isinstance(ofertas, dict):
                preco_atual = _parse_preco(ofertas.get("price") or ofertas.get("lowPrice") or ofertas.get("highPrice"))
                preco_original = _parse_preco(
                    ofertas.get("wasPrice")
                    or ofertas.get("originalPrice")
                    or ofertas.get("listPrice")
                    or ofertas.get("priceSpecification", {}).get("price")
                )
                if preco_atual and not dados.get("preco"):
                    dados["preco"] = preco_atual
                if preco_atual and preco_original:
                    dados["desconto_percent"] = max(
                        dados.get("desconto_percent", 0),
                        _calcular_desconto(preco_atual, preco_original),
                    )

            if not dados.get("preco"):
                preco = _parse_preco(item.get("offers", {}).get("price") or item.get("price"))
                if preco:
                    dados["preco"] = preco

            preco_original = _parse_preco(item.get("originalPrice") or item.get("listPrice") or item.get("wasPrice"))
            if dados.get("preco") and preco_original:
                dados["desconto_percent"] = max(
                    dados.get("desconto_percent", 0),
                    _calcular_desconto(dados["preco"], preco_original),
                )
    return dados


def _meta(soup: BeautifulSoup, propriedade: str) -> str:
    tag = soup.find("meta", property=propriedade) or soup.find("meta", attrs={"name": propriedade})
    return (tag.get("content") or "").strip() if tag else ""


def extrair_dados_produto(url: str, timeout: int = 15) -> dict:
    """Retorna {'nome': str, 'preco': float|None, 'imagem_url': str, 'desconto_percent': int}.
    Campos não encontrados voltam vazios/None — não levanta exceção por
    dado ausente, só por falha de rede/HTTP."""
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    dados = {"nome": "", "preco": None, "imagem_url": "", "desconto_percent": 0}
    dados.update({k: v for k, v in _de_json_ld(soup).items() if v not in (None, "", [], {})})

    if not dados["nome"]:
        dados["nome"] = _meta(soup, "og:title")
    if not dados["nome"] and soup.title:
        dados["nome"] = soup.title.get_text(strip=True)

    if not dados["imagem_url"]:
        dados["imagem_url"] = _meta(soup, "og:image") or _meta(soup, "twitter:image")

    preco_atual = dados.get("preco")
    if not preco_atual:
        for prop in ("product:price:amount", "og:price:amount", "twitter:price:amount", "product:price:amount"):
            preco_atual = _parse_preco(_meta(soup, prop))
            if preco_atual:
                dados["preco"] = preco_atual
                break

    for prop in ("product:original_price:amount", "product:price:original", "product:retail_price:amount", "og:price:original_amount"):
        preco_original = _parse_preco(_meta(soup, prop))
        if preco_original:
            dados["desconto_percent"] = max(
                dados.get("desconto_percent", 0),
                _calcular_desconto(dados.get("preco"), preco_original),
            )
            break

    if dados.get("preco") and not dados.get("desconto_percent"):
        preco_original = None
        for prop in ("product:price:original", "product:original_price:amount"):
            preco_original = _parse_preco(_meta(soup, prop))
            if preco_original:
                break
        if preco_original:
            dados["desconto_percent"] = _calcular_desconto(dados["preco"], preco_original)

    return dados
