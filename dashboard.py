import html
import urllib.parse

import streamlit as st

from config import (
    ADMIN_PASSWORD,
    AMAZON_ACCESS_KEY,
    AMAZON_SECRET_KEY,
    AMAZON_PARTNER_TAG,
    CHECK_INTERVAL_HOURS,
    KEYWORDS,
    MAX_PRICE,
    MIN_DISCOUNT_PERCENT,
    MIN_PRICE,
    SHOPEE_PARTNER_ID,
    SHOPEE_PARTNER_KEY,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
)
from clients import amazon_client, shopee_client
import telegram_poster

CSS = """
<style>
:root {
    --accent: #22d3ee;
    --accent-soft: rgba(34, 211, 238, 0.12);
    --ok: #34d399;
    --pending: #f87171;
    --card-bg: #141a2a;
    --card-border: rgba(255, 255, 255, 0.08);
    --text-muted: #8b93a7;
}

#MainMenu, footer, header {visibility: hidden;}

.hero {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.75rem 2rem;
    margin-bottom: 1.5rem;
    border-radius: 20px;
    background: linear-gradient(135deg, rgba(34,211,238,0.16), rgba(20,26,42,0.4));
    border: 1px solid var(--card-border);
}
.hero-emoji { font-size: 2.5rem; line-height: 1; }
.hero h1 { margin: 0; font-size: 1.7rem; }
.hero p { margin: 0.2rem 0 0; color: var(--text-muted); }

.stat-card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    height: 100%;
}
.stat-icon { font-size: 1.3rem; opacity: 0.85; }
.stat-value { font-size: 1.6rem; font-weight: 700; margin-top: 0.15rem; }
.stat-label { color: var(--text-muted); font-size: 0.85rem; }

.badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.15rem 0.65rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
}
.badge-ok { background: rgba(52, 211, 153, 0.14); color: var(--ok); }
.badge-pending { background: rgba(248, 113, 113, 0.14); color: var(--pending); }

.chip {
    display: inline-block;
    background: var(--accent-soft);
    color: var(--accent);
    border-radius: 999px;
    padding: 0.2rem 0.7rem;
    margin: 0.15rem 0.25rem 0.15rem 0;
    font-size: 0.8rem;
}

.section-title {
    font-size: 1.15rem;
    font-weight: 700;
    margin: 0.5rem 0 0.75rem;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 18px !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.35);
}

.offer-img {
    width: 100%;
    height: 150px;
    border-radius: 12px;
    background-size: cover;
    background-position: center;
    background-color: rgba(255,255,255,0.04);
    margin-bottom: 0.6rem;
}
.offer-badge {
    display: inline-block;
    background: rgba(52, 211, 153, 0.16);
    color: var(--ok);
    font-weight: 700;
    padding: 0.1rem 0.55rem;
    border-radius: 999px;
    font-size: 0.8rem;
    margin-bottom: 0.35rem;
}
.offer-title {
    font-weight: 600;
    line-height: 1.3;
    margin-bottom: 0.25rem;
    min-height: 2.6em;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}
.offer-price { font-size: 1.25rem; font-weight: 700; }
.offer-store { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.5rem; }

.stButton > button, .stLinkButton > a {
    border-radius: 10px !important;
}
</style>
"""


def _safe_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return ""
    return url.replace("'", "%27")


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def hero():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-emoji">🛒</div>
            <div>
                <h1>Painel Vendedor1</h1>
                <p>Busca ofertas, valida configurações e permite envio manual por Telegram/WhatsApp.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def stat_card(icon: str, label: str, value: str) -> str:
    return (
        f'<div class="stat-card">'
        f'<div class="stat-icon">{icon}</div>'
        f'<div class="stat-value">{html.escape(str(value))}</div>'
        f'<div class="stat-label">{html.escape(label)}</div>'
        f"</div>"
    )


def status_tag(label: str, ok: bool) -> str:
    cls = "badge-ok" if ok else "badge-pending"
    icone = "●" if ok else "○"
    return f'<span class="badge {cls}">{icone} {html.escape(label)}</span>'


def buscar_ofertas_hoje() -> list[dict]:
    ofertas = []

    for palavra in KEYWORDS:
        for cliente in (shopee_client, amazon_client):
            try:
                ofertas.extend(cliente.buscar_ofertas(palavra))
            except Exception as exc:
                st.sidebar.warning(f"Falha em {cliente.__name__}: {exc}")

    visto = set()
    unicas = []
    for oferta in ofertas:
        chave = (oferta.get("fonte"), oferta.get("id"))
        if chave in visto:
            continue
        visto.add(chave)
        unicas.append(oferta)

    return sorted(unicas, key=lambda item: item.get("desconto_percent", 0), reverse=True)


def formatar_whatsapp_link(oferta: dict) -> str:
    texto = (
        f"🔥 {oferta.get('nome', 'Oferta')}\n"
        f"💰 Preço: R$ {float(oferta.get('preco', 0)):.2f}\n"
        f"📉 Desconto: {oferta.get('desconto_percent', 0)}%\n"
        f"🛒 Loja: {oferta.get('fonte', 'Loja')}\n"
        f"👉 {oferta.get('link_afiliado', '')}"
    )
    return "https://api.whatsapp.com/send?text=" + urllib.parse.quote(texto)


def teste_telegram():
    oferta_teste = {
        "id": "teste_telegram",
        "fonte": "Teste",
        "nome": "Oferta de teste do sistema",
        "preco": 99.90,
        "desconto_percent": 25,
        "link_afiliado": "https://example.com/oferta-teste",
        "imagem_url": "",
    }
    return telegram_poster.postar_oferta(oferta_teste)


def render_offer_card(oferta: dict):
    with st.container(border=True):
        imagem = _safe_url(oferta.get("imagem_url", ""))
        if imagem:
            st.markdown(
                f'<div class="offer-img" style="background-image:url(\'{imagem}\')"></div>',
                unsafe_allow_html=True,
            )
        nome = html.escape(str(oferta.get("nome", "Oferta")))
        fonte = html.escape(str(oferta.get("fonte", "Loja")))
        st.markdown(
            f"""
            <div class="offer-badge">-{oferta.get('desconto_percent', 0)}%</div>
            <div class="offer-title">{nome}</div>
            <div class="offer-price">R$ {float(oferta.get('preco', 0)):.2f}</div>
            <div class="offer-store">{fonte}</div>
            """,
            unsafe_allow_html=True,
        )
        col_tg, col_wpp = st.columns(2)
        with col_tg:
            if st.button("📨 Telegram", key=f"telegram_{oferta.get('id')}", use_container_width=True):
                ok = telegram_poster.postar_oferta(oferta)
                st.success("Enviado!") if ok else st.error("Falha ao enviar")
        with col_wpp:
            st.link_button("💬 WhatsApp", formatar_whatsapp_link(oferta), use_container_width=True)


def render_offer_grid(ofertas: list[dict], colunas: int = 3):
    for inicio in range(0, len(ofertas), colunas):
        pedaco = ofertas[inicio:inicio + colunas]
        cols = st.columns(colunas)
        for col, oferta in zip(cols, pedaco):
            with col:
                render_offer_card(oferta)


def checar_senha() -> bool:
    if not ADMIN_PASSWORD:
        return True
    if st.session_state.get("autenticado"):
        return True

    inject_css()
    st.markdown(
        '<div class="hero"><div class="hero-emoji">🔒</div>'
        "<div><h1>Painel Vendedor1</h1><p>Acesso restrito. Digite a senha para continuar.</p></div></div>",
        unsafe_allow_html=True,
    )
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if senha == ADMIN_PASSWORD:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


def main():
    st.set_page_config(page_title="Painel Vendedor1", page_icon="🛒", layout="wide")
    if not checar_senha():
        return
    inject_css()
    hero()

    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(stat_card("🔑", "Palavras-chave", len(KEYWORDS)), unsafe_allow_html=True)
    col2.markdown(stat_card("📉", "Desconto mínimo", f"{MIN_DISCOUNT_PERCENT}%"), unsafe_allow_html=True)
    col3.markdown(stat_card("💰", "Preço mínimo", f"R$ {MIN_PRICE:.2f}"), unsafe_allow_html=True)
    col4.markdown(stat_card("⏱️", "Intervalo", f"{CHECK_INTERVAL_HOURS}h"), unsafe_allow_html=True)

    with st.sidebar:
        def config_badge(ok: bool) -> str:
            return status_tag("ok" if ok else "pendente", ok)

        st.markdown('<div class="section-title">Configuração ativa</div>', unsafe_allow_html=True)
        st.markdown(f"Telegram token: {config_badge(bool(TELEGRAM_BOT_TOKEN))}", unsafe_allow_html=True)
        st.markdown(f"Canal Telegram: {config_badge(bool(TELEGRAM_CHANNEL_ID))}", unsafe_allow_html=True)
        st.markdown(f"Amazon access key: {config_badge(bool(AMAZON_ACCESS_KEY))}", unsafe_allow_html=True)
        st.markdown(f"Amazon secret: {config_badge(bool(AMAZON_SECRET_KEY))}", unsafe_allow_html=True)
        st.markdown(f"Amazon partner tag: {config_badge(bool(AMAZON_PARTNER_TAG))}", unsafe_allow_html=True)
        st.markdown(f"Shopee partner ID: {config_badge(bool(SHOPEE_PARTNER_ID))}", unsafe_allow_html=True)
        st.markdown(f"Shopee partner key: {config_badge(bool(SHOPEE_PARTNER_KEY))}", unsafe_allow_html=True)
        st.write(f"Máximo: R$ {MAX_PRICE:.2f}")
        st.markdown('<div class="section-title">Keywords</div>', unsafe_allow_html=True)
        chips = "".join(f'<span class="chip">{html.escape(p)}</span>' for p in KEYWORDS)
        st.markdown(chips, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Status operacional</div>', unsafe_allow_html=True)
    col_status_1, col_status_2, col_status_3 = st.columns(3)
    with col_status_1:
        pronto = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID)
        st.markdown(f"**Telegram** {status_tag('pronto' if pronto else 'pendente', pronto)}", unsafe_allow_html=True)
    with col_status_2:
        pronto = bool(AMAZON_ACCESS_KEY and AMAZON_SECRET_KEY and AMAZON_PARTNER_TAG)
        st.markdown(f"**Amazon** {status_tag('pronto' if pronto else 'pendente', pronto)}", unsafe_allow_html=True)
    with col_status_3:
        pronto = bool(SHOPEE_PARTNER_ID and SHOPEE_PARTNER_KEY)
        st.markdown(f"**Shopee** {status_tag('pronto' if pronto else 'pendente', pronto)}", unsafe_allow_html=True)

    st.write("")
    row = st.columns([1, 1, 1])
    with row[0]:
        if st.button("🔎 Buscar ofertas agora", use_container_width=True):
            with st.spinner("Consultando Amazon e Shopee..."):
                ofertas = buscar_ofertas_hoje()
            st.session_state["ofertas"] = ofertas
    with row[1]:
        if st.button("📨 Testar Telegram", use_container_width=True):
            ok = teste_telegram()
            if ok:
                st.success("Mensagem de teste enviada com sucesso no Telegram.")
            else:
                st.error("Falha no teste do Telegram. Verifique o token e o canal.")
    with row[2]:
        st.button(
            "🗑️ Limpar lista",
            use_container_width=True,
            on_click=lambda: st.session_state.__setitem__("ofertas", []),
        )

    ofertas = st.session_state.get("ofertas", [])

    if ofertas:
        st.markdown(f'<div class="section-title">Ofertas encontradas: {len(ofertas)}</div>', unsafe_allow_html=True)
        render_offer_grid(ofertas)
    else:
        st.info("Ainda não houve busca. Clique em 'Buscar ofertas agora' para consultar as ofertas ativas.")


if __name__ == "__main__":
    if "ofertas" not in st.session_state:
        st.session_state["ofertas"] = []
    main()
