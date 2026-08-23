"""
Linktree pública — título, logo, cores e links são editados pelo painel
admin (aba "Linktree") e lidos daqui em tempo real, sem precisar de deploy.
"""
import base64
import os

import streamlit as st

import storage
import ui_common as ui


def main():
    kv = storage.obter_config_kv()
    titulo = kv.get("linktree_titulo", "Vendedor1")
    subtitulo = kv.get("linktree_subtitulo", "Ofertas de fitness & bem-estar todos os dias")
    cor_primaria = kv.get("linktree_cor_primaria", "#22d3ee")
    cor_fundo = kv.get("linktree_cor_fundo", "#060a14")
    logo_emoji = kv.get("linktree_logo_emoji", "🛒")

    st.set_page_config(page_title=titulo, page_icon="🔗", layout="centered")
    ui.inject_css(accent=cor_primaria, bg=cor_fundo)

    logo_html = f'<div class="hero-emoji">{logo_emoji}</div>'
    caminho_logo = ui.logo_path()
    if os.path.exists(caminho_logo):
        with open(caminho_logo, "rb") as arquivo:
            b64 = base64.b64encode(arquivo.read()).decode("ascii")
        logo_html = (
            f'<img src="data:image/png;base64,{b64}" '
            f'style="width:64px;height:64px;border-radius:50%;object-fit:cover;" />'
        )

    st.markdown(
        f"""
        <div style="text-align:center; margin: 2rem 0 1.5rem;">
            {logo_html}
            <h1 style="margin:0.5rem 0 0;">{titulo}</h1>
            <p style="color:var(--text-muted);">{subtitulo}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    links = storage.listar_links(somente_ativos=True)
    if not links:
        st.info("Nenhum link configurado ainda.")
        return

    html_links = "".join(
        f'<a class="link-card" href="{ui.safe_url(link["url"])}" target="_blank" rel="noopener">'
        f'<span class="emoji">{link["emoji"]}</span><span>{link["label"]}</span></a>'
        for link in links
        if ui.safe_url(link["url"])
    )
    st.markdown(html_links, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
