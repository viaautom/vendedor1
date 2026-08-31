"""
Design system compartilhado entre os apps Streamlit do projeto
(dashboard.py, loja.py, linktree.py): CSS "futurista" (painéis translúcidos,
glow neon, grid de fundo) e helpers de card reaproveitados por todos.
"""
import html
import os

import streamlit as st

import config

MONO_FONT = "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def base_css(accent: str = "#0ea5e9", accent2: str = "#7c3aed", bg: str = "#eef4fb") -> str:
    return f"""
    <style>
    :root {{
        --accent: {accent};
        --accent-2: {accent2};
        --accent-soft: {accent}18;
        --ok: #16a34a;
        --pending: #ef4444;
        --bg: {bg};
        --card-bg: rgba(255, 255, 255, 0.9);
        --card-border: rgba(148, 163, 184, 0.28);
        --text-muted: #53627a;
        --mono: {MONO_FONT};
        --text: #111827;
    }}

    #MainMenu, footer, header {{visibility: hidden;}}

    .stApp {{
        background:
            radial-gradient(circle at top left, rgba(14, 165, 233, 0.12), transparent 25%),
            radial-gradient(circle at bottom right, rgba(124, 58, 237, 0.1), transparent 22%),
            linear-gradient(180deg, #f7fbff 0%, var(--bg) 100%);
        color: var(--text);
    }}

    .hero {{
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1.75rem 2rem;
        margin-bottom: 1.5rem;
        border-radius: 20px;
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.10), rgba(124, 58, 237, 0.04));
        border: 1px solid rgba(148, 163, 184, 0.20);
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
    }}
    .hero-emoji {{ font-size: 2.5rem; line-height: 1; }}
    .hero h1 {{ margin: 0; font-size: 1.7rem; color: var(--text); }}
    .hero p {{ margin: 0.2rem 0 0; color: var(--text-muted); }}

    .stat-card {{
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        height: 100%;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04);
    }}
    .stat-icon {{ font-size: 1.3rem; opacity: 0.85; }}
    .stat-value {{ font-size: 1.6rem; font-weight: 700; margin-top: 0.15rem; font-family: var(--mono); }}
    .stat-label {{ color: var(--text-muted); font-size: 0.85rem; }}

    .badge {{
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.15rem 0.65rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        font-family: var(--mono);
    }}
    .badge-ok {{ background: rgba(52, 211, 153, 0.14); color: var(--ok); }}
    .badge-pending {{ background: rgba(248, 113, 113, 0.14); color: var(--pending); }}

    .chip {{
        display: inline-block;
        background: var(--accent-soft);
        color: var(--accent);
        border-radius: 999px;
        padding: 0.2rem 0.7rem;
        margin: 0.15rem 0.25rem 0.15rem 0;
        font-size: 0.8rem;
        font-family: var(--mono);
    }}

    .section-title {{
        font-size: 1.15rem;
        font-weight: 700;
        margin: 0.5rem 0 0.75rem;
    }}

    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: 18px !important;
        border-color: var(--card-border) !important;
        background: var(--card-bg) !important;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
    }}

    .offer-img {{
        width: 100%;
        height: 190px;
        border-radius: 12px;
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
        background-color: rgba(255,255,255,0.04);
        margin-bottom: 0.6rem;
    }}
    @media (max-width: 640px) {{
        .offer-img {{ height: 220px; }}
        .hero {{ padding: 1.25rem 1.4rem; }}
        .hero h1 {{ font-size: 1.4rem; }}
    }}
    .offer-thumb {{
        width: 64px;
        height: 64px;
        border-radius: 10px;
        background-size: cover;
        background-position: center;
        background-color: rgba(255,255,255,0.04);
        border: 1px solid var(--card-border);
    }}
    .offer-row-title {{ font-weight: 600; }}
    .offer-row-meta {{ color: var(--text-muted); font-size: 0.8rem; font-family: var(--mono); }}
    .offer-badge {{
        display: inline-block;
        background: rgba(52, 211, 153, 0.16);
        color: var(--ok);
        font-weight: 700;
        padding: 0.1rem 0.55rem;
        border-radius: 999px;
        font-size: 0.8rem;
        margin-bottom: 0.35rem;
        font-family: var(--mono);
    }}
    .offer-title {{
        font-weight: 600;
        line-height: 1.3;
        margin-bottom: 0.25rem;
        min-height: 2.6em;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }}
    .offer-price {{ font-size: 1.25rem; font-weight: 700; font-family: var(--mono); }}
    .offer-store {{ color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.25rem; }}
    .offer-meta {{ color: var(--text-muted); font-size: 0.75rem; margin-bottom: 0.5rem; font-family: var(--mono); }}

    .send-status {{ display: flex; gap: 0.5rem; margin-bottom: 0.5rem; font-size: 1.1rem; }}
    .send-status .off {{ opacity: 0.28; filter: grayscale(1); }}
    .send-status .on {{ opacity: 1; filter: none; text-shadow: 0 0 8px currentColor; }}

    .link-card, .link-card *,
    .product-card, .product-card *,
    .banner-card, .banner-card * {{
        text-decoration: none !important;
        color: inherit !important;
    }}

    .link-card {{
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.9rem 1.1rem;
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 14px;
        font-weight: 600;
        margin-bottom: 0.85rem;
        backdrop-filter: blur(8px);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    .link-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 0 24px {accent}33;
        border-color: {accent};
    }}
    .link-card .emoji {{ font-size: 1.3rem; }}

    .product-card {{
        display: block;
    }}
    .product-card:hover .offer-title {{
        color: var(--accent) !important;
    }}
    .featured-card {{
        display: block;
        border: 1px solid {accent}80;
        border-radius: 16px;
        padding: 0.5rem;
        box-shadow: 0 0 22px {accent}26;
    }}

    .banner-card {{
        display: block;
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid var(--card-border);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    .banner-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 0 28px {accent}33;
    }}
    .banner-card img {{
        width: 100%;
        height: auto;
        display: block;
    }}

    .stButton > button, .stLinkButton > a {{
        border-radius: 10px !important;
        border: 1px solid rgba(148, 163, 184, 0.35) !important;
        background: linear-gradient(180deg, #ffffff, #f3f8ff) !important;
        color: var(--text) !important;
        box-shadow: 0 4px 10px rgba(15, 23, 42, 0.04) !important;
    }}
    .stButton > button:hover, .stLinkButton > a:hover {{
        border-color: var(--accent) !important;
        box-shadow: 0 8px 16px rgba(14, 165, 233, 0.12) !important;
    }}
    </style>
    """


def inject_css(accent: str = "#22d3ee", accent2: str = "#8b5cf6", bg: str = "#060a14"):
    st.markdown(base_css(accent, accent2, bg), unsafe_allow_html=True)


def hero(icon: str, titulo: str, subtitulo: str):
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-emoji">{icon}</div>
            <div>
                <h1>{html.escape(titulo)}</h1>
                <p>{html.escape(subtitulo)}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def stat_card(icon: str, label: str, value) -> str:
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


def safe_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith(("http://", "https://", "data:image/", "file://")):
        return url.replace("'", "%27")
    return ""


def oferta_card_inner_html(oferta: dict) -> str:
    imagem = safe_url(oferta.get("imagem_url", ""))
    nome = html.escape(str(oferta.get("nome", "Oferta")))
    fonte = html.escape(str(oferta.get("fonte", "Loja")))
    desconto = oferta.get("desconto_percent", 0) or 0
    partes = []
    if imagem:
        partes.append(f'<div class="offer-img" style="background-image:url(\'{imagem}\')"></div>')
    if desconto > 0:
        partes.append(f'<div class="offer-badge">-{desconto}%</div>')
    partes.append(f'<div class="offer-title">{nome}</div>')
    partes.append(f'<div class="offer-price">R$ {float(oferta.get("preco", 0) or 0):.2f}</div>')
    partes.append(f'<div class="offer-store">{fonte}</div>')
    return "".join(partes)


def banner_html(banner: dict, altura: int = 180) -> str:
    imagem = safe_url(banner.get("imagem_url", ""))
    link = safe_url(banner.get("link_url", ""))
    if not imagem:
        return ""
    conteudo = f'<div class="banner-card"><img src="{imagem}" alt="banner"></div>'
    if link:
        return f'<a href="{link}" target="_blank" rel="noopener">{conteudo}</a>'
    return conteudo


def thumb_html(imagem_url: str) -> str:
    imagem = safe_url(imagem_url)
    if not imagem:
        return '<div class="offer-thumb"></div>'
    return f'<div class="offer-thumb" style="background-image:url(\'{imagem}\')"></div>'


def logo_path() -> str:
    diretorio = os.path.dirname(os.path.abspath(config.DATABASE_PATH))
    return os.path.join(diretorio, "logo.png")


def send_status_html(enviado_telegram: bool, enviado_whatsapp: bool, enviado_whatsapp_grupo: bool = False) -> str:
    tg_cls = "on" if enviado_telegram else "off"
    wa_cls = "on" if enviado_whatsapp else "off"
    wg_cls = "on" if enviado_whatsapp_grupo else "off"
    return (
        '<div class="send-status">'
        f'<span class="{tg_cls}" style="color:#29a9eb" title="Telegram">📨</span>'
        f'<span class="{wa_cls}" style="color:#25d366" title="WhatsApp (pessoal)">💬</span>'
        f'<span class="{wg_cls}" style="color:#25d366" title="Grupo do WhatsApp">📲</span>'
        "</div>"
    )
