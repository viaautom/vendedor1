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


def _de_json_ld(soup: BeautifulSoup) -> dict:
    dados = {}
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
            if isinstance(ofertas, dict) and not dados.get("preco"):
                preco = _parse_preco(ofertas.get("price") or ofertas.get("lowPrice"))
                if preco:
                    dados["preco"] = preco
    return dados


def _meta(soup: BeautifulSoup, propriedade: str) -> str:
    tag = soup.find("meta", property=propriedade) or soup.find("meta", attrs={"name": propriedade})
    return (tag.get("content") or "").strip() if tag else ""


def extrair_dados_produto(url: str, timeout: int = 15) -> dict:
    """Retorna {'nome': str, 'preco': float|None, 'imagem_url': str}.
    Campos não encontrados voltam vazios/None — não levanta exceção por
    dado ausente, só por falha de rede/HTTP."""
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    dados = {"nome": "", "preco": None, "imagem_url": ""}
    dados.update({k: v for k, v in _de_json_ld(soup).items() if v})

    if not dados["nome"]:
        dados["nome"] = _meta(soup, "og:title")
    if not dados["nome"] and soup.title:
        dados["nome"] = soup.title.get_text(strip=True)

    if not dados["imagem_url"]:
        dados["imagem_url"] = _meta(soup, "og:image")

    if not dados["preco"]:
        for prop in ("product:price:amount", "og:price:amount"):
            preco = _parse_preco(_meta(soup, prop))
            if preco:
                dados["preco"] = preco
                break

    return dados
