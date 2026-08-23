"""
Vitrine pública de ofertas — mostra só o que está disponível no
repositório (storage.ofertas_encontradas), agrupado por nicho. Sem senha,
sem ações server-side: cada card é um link direto pra página de vendas.
Título, subtítulo e banners promocionais são editados pelo painel admin
(aba "🛍️ Vitrine") e lidos daqui em tempo real.
"""
import streamlit as st

import storage
import ui_common as ui


def render_produto(oferta: dict) -> str:
    link = ui.safe_url(oferta.get("link_afiliado", ""))
    if not link:
        return ""
    return f'<a class="product-card" href="{link}" target="_blank" rel="noopener">' + ui.oferta_card_inner_html(oferta) + "</a>"


def main():
    kv = storage.obter_config_kv()
    titulo = kv.get("loja_titulo", "Vitrine Vendedor1")
    subtitulo = kv.get("loja_subtitulo", "As melhores ofertas de fitness & bem-estar, atualizadas automaticamente.")

    st.set_page_config(page_title=titulo, page_icon="🛍️", layout="wide")
    ui.inject_css()
    ui.hero("🛍️", titulo, subtitulo)

    banners = storage.listar_banners(somente_ativos=True)
    if banners:
        cols = st.columns(min(len(banners), 3) or 1)
        for idx, banner in enumerate(banners):
            html = ui.banner_html(banner)
            if html:
                with cols[idx % len(cols)]:
                    st.markdown(html, unsafe_allow_html=True)
        st.write("")

    ofertas = storage.listar_ofertas(somente_disponiveis=True)
    if not ofertas:
        st.info("Nenhuma oferta disponível no momento. Volte em breve!")
        return

    por_nicho: dict[str, list[dict]] = {}
    for oferta in ofertas:
        nicho = oferta.get("keyword") or "Outros"
        por_nicho.setdefault(nicho, []).append(oferta)

    for nicho, itens in por_nicho.items():
        st.markdown(f'<div class="section-title">🏷️ {nicho} ({len(itens)})</div>', unsafe_allow_html=True)
        cols = st.columns(3)
        for idx, oferta in enumerate(itens):
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(render_produto(oferta), unsafe_allow_html=True)
        st.write("")


if __name__ == "__main__":
    main()
