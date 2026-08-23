"""
Vitrine pública de ofertas — mostra só o que está disponível no
repositório (storage.ofertas_encontradas), agrupado por nicho. Sem senha,
sem ações server-side: cada card é um link direto pra página de vendas.
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
    st.set_page_config(page_title="Vitrine Vendedor1", page_icon="🛍️", layout="wide")
    ui.inject_css()
    ui.hero("🛍️", "Vitrine Vendedor1", "As melhores ofertas de fitness & bem-estar, atualizadas automaticamente.")

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
