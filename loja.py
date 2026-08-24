"""
Vitrine pública de ofertas — mostra só o que está disponível no
repositório (storage.ofertas_encontradas). Produtos marcados como
destaque aparecem numa seção fixa no topo; os demais ficam organizados
por nicho, em seções que abrem com clique. Sem senha, sem ações
server-side: cada card é um link direto pra página de vendas. Título,
subtítulo e banners são editados no painel admin (aba "🛍️ Vitrine").
"""
import streamlit as st
import re

import storage
import ui_common as ui


def render_produto(oferta: dict, destaque: bool = False) -> str:
    link = ui.safe_url(oferta.get("link_afiliado", ""))
    if not link:
        return ""
    classe = "product-card featured-card" if destaque else "product-card"
    return f'<a class="{classe}" href="{link}" target="_blank" rel="noopener">' + ui.oferta_card_inner_html(oferta) + "</a>"


def render_produtos_grid(itens: list[dict], destaque: bool = False, colunas: int = 3):
    cols = st.columns(colunas)
    for idx, oferta in enumerate(itens):
        with cols[idx % colunas]:
            with st.container(border=True):
                st.markdown(render_produto(oferta, destaque), unsafe_allow_html=True)


def main():
    if not st.session_state.get("acesso_registrado"):
        storage.registrar_acesso("vitrine")
        st.session_state["acesso_registrado"] = True

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
            banner_html = ui.banner_html(banner)
            if banner_html:
                with cols[idx % len(cols)]:
                    st.markdown(banner_html, unsafe_allow_html=True)
        st.write("")

    ofertas = storage.listar_ofertas(somente_disponiveis=True)
    if not ofertas:
        st.info("Nenhuma oferta disponível no momento. Volte em breve!")
    else:
        destacados = [o for o in ofertas if o.get("destaque")]
        if destacados:
            st.markdown(f'<div class="section-title">⭐ Destaques ({len(destacados)})</div>', unsafe_allow_html=True)
            render_produtos_grid(destacados, destaque=True)
            st.write("")

        por_nicho: dict[str, list[dict]] = {}
        for oferta in ofertas:
            nicho = oferta.get("keyword") or "Outros"
            por_nicho.setdefault(nicho, []).append(oferta)

        st.markdown('<div class="section-title">🗂️ Categorias</div>', unsafe_allow_html=True)
        for nicho, itens in por_nicho.items():
            with st.expander(f"🏷️ {nicho} ({len(itens)})"):
                render_produtos_grid(itens)

    with st.expander("📩 Receba novas ofertas"):
        with st.form("form_lead_vitrine", clear_on_submit=True):
            nome = st.text_input("Seu nome *")
            email = st.text_input("Seu e-mail *")
            whatsapp = st.text_input("WhatsApp")
            consentimento = st.checkbox("Aceito receber ofertas e novidades.")
            if st.form_submit_button("Cadastrar"):
                email_valido = re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip())
                if not nome.strip() or not email_valido:
                    st.warning("Informe nome e um e-mail válido.")
                elif not consentimento:
                    st.warning("Confirme o aceite para receber as ofertas.")
                elif storage.salvar_lead(nome, email, whatsapp, "vitrine"):
                    st.success("Cadastro realizado. Obrigado!")
                else:
                    st.info("Esse e-mail já está cadastrado.")


if __name__ == "__main__":
    main()
