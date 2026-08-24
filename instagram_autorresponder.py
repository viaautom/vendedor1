import re
from typing import Iterable

import storage


def extrair_ids_de_texto(texto: str) -> list[str]:
    """Extrai IDs do formato #id1-id2-id3 da mensagem do Instagram.
    Também aceita IDs curtos sem hífen, como #PWHEYC72414.
    """
    if not texto:
        return []

    tokens = []
    for match in re.finditer(r"#([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)", texto):
        bloco = match.group(1).strip()
        if not bloco:
            continue
        partes = [parte for parte in bloco.split("-") if parte.strip()]
        tokens.extend(partes)

    return tokens


def buscar_pecas_por_ids(ids: Iterable[str]) -> list[dict]:
    """Busca as ofertas pelo ID curto usando o repositório local."""
    ids = [str(item).strip() for item in ids if str(item).strip()]
    if not ids:
        return []

    ofertas = []
    for oferta in storage.listar_ofertas(somente_disponiveis=False):
        if oferta.get("id") in ids:
            ofertas.append(oferta)

    return ofertas


def montar_mensagem(ofertas: list[dict]) -> str:
    """Gera a mensagem padrão para responder no Instagram."""
    if not ofertas:
        return "Nenhuma peça encontrada com esses IDs."

    linhas = [
        "Oi! 💖 Vi que você comentou no post e se",
        "interessou pelas peças!",
        "",
        "Aqui estão os links diretos para você",
        "conferir:",
        "",
    ]

    for oferta in ofertas:
        nome = (oferta.get("nome") or "Peça").strip()
        link = (oferta.get("link_afiliado") or "").strip()
        linhas.append(f"👘 **{nome}**")
        linhas.append(f"➡️ [{link}]({link})")
        linhas.append("")

    linhas.extend([
        "Qualquer dúvida com tamanhos ou detalhes, é",
        "só me chamar! 😉",
    ])

    return "\n".join(linhas)


def processar_comentario(texto: str) -> str:
    ids = extrair_ids_de_texto(texto)
    ofertas = buscar_pecas_por_ids(ids)
    return montar_mensagem(ofertas)


if __name__ == "__main__":
    exemplo = "#id1 #id2 #P-whey-prote-C72414"
    print(processar_comentario(exemplo))
