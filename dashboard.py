import hashlib
import re
import urllib.parse
from datetime import datetime

import streamlit as st

from config import (
    ADMIN_PASSWORD,
    AMAZON_ACCESS_KEY,
    AMAZON_SECRET_KEY,
    AMAZON_PARTNER_TAG,
    SHOPEE_PARTNER_ID,
    SHOPEE_PARTNER_KEY,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
)
from clients import amazon_client, shopee_client
import settings
import storage
import telegram_poster
import whatsapp_client
import ui_common as ui


def checar_senha() -> bool:
    if not ADMIN_PASSWORD:
        return True
    if st.session_state.get("autenticado"):
        return True

    ui.inject_css()
    ui.hero("🔒", "Painel Vendedor1", "Acesso restrito. Digite a senha para continuar.")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if senha == ADMIN_PASSWORD:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


def formatar_whatsapp_link(oferta: dict) -> str:
    texto = (
        f"🔥 {oferta.get('nome', 'Oferta')}\n"
        f"💰 Preço: R$ {float(oferta.get('preco', 0) or 0):.2f}\n"
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


def buscar_e_persistir(cfg: dict):
    for palavra in cfg["keywords"]:
        for cliente, fonte in ((shopee_client, "Shopee"), (amazon_client, "Amazon")):
            try:
                ofertas = cliente.buscar_ofertas(
                    palavra, min_discount_percent=cfg["min_discount_percent"]
                )
            except Exception as exc:
                st.sidebar.warning(f"Falha em {fonte} ('{palavra}'): {exc}")
                continue

            for oferta in ofertas:
                oferta["keyword"] = palavra
            ofertas = settings.filtrar_por_preco(ofertas, cfg)

            for oferta in ofertas:
                storage.registrar_oferta(oferta)
            ids_vistos = {oferta["id"] for oferta in ofertas}
            storage.marcar_indisponiveis(palavra, fonte, ids_vistos)


def id_manual(link: str) -> str:
    return "manual_" + hashlib.md5(link.strip().encode("utf-8")).hexdigest()[:12]


def nome_a_partir_do_link(link: str) -> str:
    """Tenta um nome razoável a partir do próprio link, já que o link é o
    único dado obrigatório no cadastro manual. Pega o segmento do caminho
    com mais palavras (o slug do título) em vez de sempre o último — em
    links tipo Amazon (/titulo-do-produto/dp/ASIN) o último segmento é só
    o código do produto, não o título."""
    caminho = urllib.parse.urlparse(link).path
    melhor = ""
    for segmento in caminho.split("/"):
        if not segmento:
            continue
        limpo = urllib.parse.unquote(segmento)
        limpo = re.sub(r"\.(html?|php|aspx?)$", "", limpo, flags=re.IGNORECASE)
        limpo = re.sub(r"[-_+]+", " ", limpo).strip()
        if len(limpo.split()) > len(melhor.split()):
            melhor = limpo
    return melhor.title() if melhor else "Produto"


def detectar_nicho(link: str, keywords: list[str]) -> str:
    """Casa palavras das keywords configuradas contra o texto do link para
    sugerir o nicho automaticamente."""
    texto = urllib.parse.unquote(link).lower()
    for kw in keywords:
        palavras = [p for p in kw.lower().split() if len(p) > 3]
        if any(p in texto for p in palavras):
            return kw
    return keywords[0] if keywords else "geral"


def formatar_data(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "—"


def render_offer_card(oferta: dict, grupos: list[dict]):
    with st.container(border=True):
        st.markdown(ui.oferta_card_inner_html(oferta), unsafe_allow_html=True)
        st.markdown(
            f'<div class="offer-meta">🏷️ {oferta.get("keyword", "—")} · '
            f'🕓 {formatar_data(oferta.get("ultima_vez_em"))} · '
            f'{"🟢 disponível" if oferta.get("disponivel") else "🔴 esgotado"}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            ui.send_status_html(
                bool(oferta.get("enviado_telegram")),
                bool(oferta.get("enviado_whatsapp")),
                bool(oferta.get("enviado_whatsapp_grupo")),
            ),
            unsafe_allow_html=True,
        )
        col_tg, col_wpp, col_conf = st.columns([1, 1, 1])
        with col_tg:
            if st.button("📨 Telegram", key=f"telegram_{oferta['id']}", use_container_width=True):
                ok = telegram_poster.postar_oferta(oferta)
                if ok:
                    storage.marcar_enviado(oferta["id"], "telegram")
                    st.rerun()
                else:
                    st.error("Falha ao enviar")
        with col_wpp:
            st.link_button("💬 Abrir", formatar_whatsapp_link(oferta), use_container_width=True)
        with col_conf:
            if st.button("✓ Enviado", key=f"wa_confirma_{oferta['id']}", use_container_width=True):
                storage.marcar_enviado(oferta["id"], "whatsapp")
                st.rerun()

        if grupos:
            if st.button("📲 Enviar aos grupos", key=f"grupo_{oferta['id']}", use_container_width=True):
                texto = whatsapp_client.formatar_mensagem(oferta)
                sucesso_algum = any(
                    whatsapp_client.enviar_mensagem(grupo["jid"], texto) for grupo in grupos
                )
                if sucesso_algum:
                    storage.marcar_enviado(oferta["id"], "whatsapp_grupo")
                    st.success("Enviado aos grupos.")
                    st.rerun()
                else:
                    st.error("Falha ao enviar — confira a conexão em '📲 Grupos'.")


def render_offer_grid(ofertas: list[dict], colunas: int = 3):
    grupos = storage.grupos_ativos()
    for inicio in range(0, len(ofertas), colunas):
        pedaco = ofertas[inicio:inicio + colunas]
        cols = st.columns(colunas)
        for col, oferta in zip(cols, pedaco):
            with col:
                render_offer_card(oferta, grupos)


def render_offer_grid_agrupado(ofertas: list[dict], colunas: int = 3):
    por_nicho: dict[str, list[dict]] = {}
    for oferta in ofertas:
        nicho = oferta.get("keyword") or "Outros"
        por_nicho.setdefault(nicho, []).append(oferta)

    for nicho, itens in por_nicho.items():
        st.markdown(f'<div class="section-title">🏷️ {nicho} ({len(itens)})</div>', unsafe_allow_html=True)
        render_offer_grid(itens, colunas)
        st.write("")


def view_ofertas(cfg: dict):
    todas = storage.listar_ofertas()
    disponiveis = [o for o in todas if o.get("disponivel")]
    nao_enviados = storage.contagem_nao_enviados()
    enviados_hoje = storage.contagem_enviados_hoje()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.markdown(ui.stat_card("🔗", "Total de links", len(todas)), unsafe_allow_html=True)
    col2.markdown(ui.stat_card("📭", "Não enviados", nao_enviados), unsafe_allow_html=True)
    col3.markdown(ui.stat_card("🟢", "Disponíveis", len(disponiveis)), unsafe_allow_html=True)
    col4.markdown(ui.stat_card("📉", "Desconto mínimo", f"{cfg['min_discount_percent']}%"), unsafe_allow_html=True)
    col5.markdown(ui.stat_card("⏱️", "Intervalo", f"{cfg['check_interval_hours']}h"), unsafe_allow_html=True)

    with st.expander("📊 Ver total de links por nicho"):
        for linha in storage.contagem_por_nicho():
            st.markdown(
                f'<span class="chip">{linha["keyword"]}: <strong>{linha["total"]}</strong></span>',
                unsafe_allow_html=True,
            )

    st.write("")
    st.markdown('<div class="section-title">Enviados hoje</div>', unsafe_allow_html=True)
    col_tg, col_wa, col_wg = st.columns(3)
    col_tg.markdown(ui.stat_card("📨", "Telegram", enviados_hoje["telegram"]), unsafe_allow_html=True)
    col_wa.markdown(ui.stat_card("💬", "WhatsApp (pessoal)", enviados_hoje["whatsapp"]), unsafe_allow_html=True)
    col_wg.markdown(ui.stat_card("📲", "Grupos WhatsApp", enviados_hoje["whatsapp_grupo"]), unsafe_allow_html=True)

    st.write("")
    row = st.columns([1, 1, 1])
    with row[0]:
        if st.button("🔎 Buscar ofertas agora", use_container_width=True):
            with st.spinner("Consultando Amazon e Shopee..."):
                buscar_e_persistir(cfg)
            st.rerun()
    with row[1]:
        if st.button("📨 Testar Telegram", use_container_width=True):
            ok = teste_telegram()
            st.success("Mensagem de teste enviada.") if ok else st.error("Falha no teste do Telegram.")
    with row[2]:
        mostrar_todas = st.toggle("Mostrar esgotados", value=True)

    with st.expander("➕ Adicionar oferta manualmente (colar link)"):
        st.caption(
            "Só o link e o preço são obrigatórios — nome, nicho e desconto são "
            "preenchidos automaticamente (e podem ser ajustados aqui se quiser)."
        )
        with st.form("form_manual", clear_on_submit=True):
            link = st.text_input("Link do produto (afiliado) *")
            c1, c2 = st.columns(2)
            preco = c1.number_input("Preço (R$) *", min_value=0.0, step=0.01)
            desconto = c2.number_input(
                "Desconto (%)", min_value=0, max_value=100, step=1, value=cfg["min_discount_percent"]
            )
            with st.expander("Ajustar nome/nicho/imagem (opcional)"):
                nome_manual = st.text_input("Nome do produto (deixe em branco para detectar do link)")
                nicho_manual = st.selectbox("Nicho", options=["(detectar automaticamente)"] + cfg["keywords"])
                imagem_url = st.text_input("URL da imagem")
                fonte = st.text_input("Loja/fonte", value="Manual")
            if st.form_submit_button("Adicionar ao repositório"):
                if link and preco:
                    storage.registrar_oferta(
                        {
                            "id": id_manual(link),
                            "fonte": fonte or "Manual",
                            "keyword": nicho_manual
                            if nicho_manual != "(detectar automaticamente)"
                            else detectar_nicho(link, cfg["keywords"]),
                            "nome": nome_manual or nome_a_partir_do_link(link),
                            "preco": preco,
                            "desconto_percent": int(desconto),
                            "link_afiliado": link,
                            "imagem_url": imagem_url,
                        }
                    )
                    st.success("Oferta adicionada. Já aparece na lista e na vitrine pública.")
                    st.rerun()
                else:
                    st.warning("Preencha ao menos o link e o preço.")

    ofertas = todas if mostrar_todas else disponiveis
    if ofertas:
        st.markdown(f'<div class="section-title">Ofertas no repositório: {len(ofertas)}</div>', unsafe_allow_html=True)
        render_offer_grid_agrupado(ofertas)
    else:
        st.info("Nenhuma oferta no repositório ainda. Clique em 'Buscar ofertas agora' ou adicione uma manualmente.")


def view_configuracoes(cfg: dict):
    st.markdown('<div class="section-title">Filtros e busca</div>', unsafe_allow_html=True)
    with st.form("form_config"):
        keywords_texto = st.text_area(
            "Palavras-chave (uma por linha)", value="\n".join(cfg["keywords"]), height=160
        )
        c1, c2 = st.columns(2)
        min_discount = c1.number_input(
            "Desconto mínimo (%)", min_value=0, max_value=100, value=cfg["min_discount_percent"]
        )
        intervalo = c2.number_input(
            "Intervalo de busca (horas)", min_value=1, max_value=168, value=cfg["check_interval_hours"]
        )
        c3, c4 = st.columns([2, 1])
        preco_min = c3.number_input("Preço mínimo (R$)", min_value=0.0, value=float(cfg["min_price"]), step=1.0)
        aplica_preco_min = c4.checkbox("Não se aplica", value=not cfg["min_price_aplica"])
        preco_max = st.number_input("Preço máximo (R$)", min_value=0.0, value=float(cfg["max_price"]), step=1.0)

        if st.form_submit_button("💾 Salvar configurações"):
            novas = {
                "keywords": [linha.strip() for linha in keywords_texto.split("\n") if linha.strip()],
                "min_discount_percent": int(min_discount),
                "min_price": float(preco_min),
                "min_price_aplica": not aplica_preco_min,
                "max_price": float(preco_max),
                "check_interval_hours": int(intervalo),
            }
            settings.salvar_configuracoes(novas)
            st.success("Configurações salvas. O worker aplica o novo intervalo no próximo ciclo.")
            st.rerun()

    st.markdown('<div class="section-title">Credenciais (via .env / Dokploy)</div>', unsafe_allow_html=True)
    st.caption("Essas não são editáveis por aqui — são segredos de infraestrutura.")
    st.markdown(f"Telegram: {ui.status_tag('ok' if TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID else 'pendente', bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID))}", unsafe_allow_html=True)
    st.markdown(f"Amazon: {ui.status_tag('ok' if AMAZON_ACCESS_KEY and AMAZON_SECRET_KEY and AMAZON_PARTNER_TAG else 'pendente', bool(AMAZON_ACCESS_KEY and AMAZON_SECRET_KEY and AMAZON_PARTNER_TAG))}", unsafe_allow_html=True)
    st.markdown(f"Shopee: {ui.status_tag('ok' if SHOPEE_PARTNER_ID and SHOPEE_PARTNER_KEY else 'pendente', bool(SHOPEE_PARTNER_ID and SHOPEE_PARTNER_KEY))}", unsafe_allow_html=True)


def view_linktree():
    links = storage.listar_links()
    kv = storage.obter_config_kv()

    st.markdown('<div class="section-title">Identidade</div>', unsafe_allow_html=True)
    with st.form("form_linktree_identidade"):
        titulo = st.text_input("Título", value=kv.get("linktree_titulo", "Vendedor1"))
        subtitulo = st.text_input(
            "Subtítulo", value=kv.get("linktree_subtitulo", "Ofertas de fitness & bem-estar todos os dias")
        )
        c1, c2 = st.columns(2)
        cor_primaria = c1.color_picker("Cor primária", value=kv.get("linktree_cor_primaria", "#22d3ee"))
        cor_fundo = c2.color_picker("Cor de fundo", value=kv.get("linktree_cor_fundo", "#060a14"))
        logo_emoji = st.text_input("Emoji do logo (usado se não houver imagem)", value=kv.get("linktree_logo_emoji", "🛒"))
        logo_upload = st.file_uploader("Logo (imagem, opcional)", type=["png", "jpg", "jpeg"])
        if st.form_submit_button("💾 Salvar identidade"):
            storage.definir_config_kv(
                {
                    "linktree_titulo": titulo,
                    "linktree_subtitulo": subtitulo,
                    "linktree_cor_primaria": cor_primaria,
                    "linktree_cor_fundo": cor_fundo,
                    "linktree_logo_emoji": logo_emoji,
                }
            )
            if logo_upload is not None:
                with open(ui.logo_path(), "wb") as arquivo:
                    arquivo.write(logo_upload.getvalue())
            st.success("Identidade da linktree salva.")
            st.rerun()

    st.markdown('<div class="section-title">Links</div>', unsafe_allow_html=True)
    if "linktree_edit" not in st.session_state:
        st.session_state["linktree_edit"] = links or [{"label": "", "url": "", "emoji": "🔗", "ativo": True}]

    with st.form("form_linktree_links"):
        editados = []
        for idx, link in enumerate(st.session_state["linktree_edit"]):
            c1, c2, c3, c4 = st.columns([1, 3, 4, 1])
            emoji = c1.text_input("Ícone", value=link.get("emoji", "🔗"), key=f"lk_emoji_{idx}")
            label = c2.text_input("Nome", value=link.get("label", ""), key=f"lk_label_{idx}")
            url = c3.text_input("URL", value=link.get("url", ""), key=f"lk_url_{idx}")
            ativo = c4.checkbox("Ativo", value=bool(link.get("ativo", True)), key=f"lk_ativo_{idx}")
            editados.append({"label": label, "url": url, "emoji": emoji, "ativo": ativo})

        col_add, col_save = st.columns(2)
        adicionar = col_add.form_submit_button("➕ Adicionar linha")
        salvar = col_save.form_submit_button("💾 Salvar links")

        if adicionar:
            editados.append({"label": "", "url": "", "emoji": "🔗", "ativo": True})
            st.session_state["linktree_edit"] = editados
            st.rerun()
        if salvar:
            validos = [link for link in editados if link["label"] and link["url"]]
            storage.salvar_links(validos)
            st.session_state["linktree_edit"] = validos or editados
            st.success("Links salvos.")
            st.rerun()


def view_vitrine():
    kv = storage.obter_config_kv()

    st.markdown('<div class="section-title">Identidade da vitrine</div>', unsafe_allow_html=True)
    with st.form("form_vitrine_identidade"):
        titulo = st.text_input("Título", value=kv.get("loja_titulo", "Vitrine Vendedor1"))
        subtitulo = st.text_input(
            "Subtítulo",
            value=kv.get(
                "loja_subtitulo",
                "As melhores ofertas de fitness & bem-estar, atualizadas automaticamente.",
            ),
        )
        if st.form_submit_button("💾 Salvar identidade"):
            storage.definir_config_kv({"loja_titulo": titulo, "loja_subtitulo": subtitulo})
            st.success("Identidade da vitrine salva.")
            st.rerun()

    st.markdown('<div class="section-title">Banners (topo da vitrine)</div>', unsafe_allow_html=True)
    st.caption("Aparecem no topo de /site, antes das ofertas. Cole a URL de uma imagem já hospedada.")

    banners_salvos = storage.listar_banners()
    if "vitrine_banners_edit" not in st.session_state:
        st.session_state["vitrine_banners_edit"] = banners_salvos or [
            {"imagem_url": "", "link_url": "", "ativo": True}
        ]

    with st.form("form_vitrine_banners"):
        editados = []
        for idx, banner in enumerate(st.session_state["vitrine_banners_edit"]):
            c1, c2, c3 = st.columns([4, 4, 1])
            imagem_url = c1.text_input("URL da imagem", value=banner.get("imagem_url", ""), key=f"bn_img_{idx}")
            link_url = c2.text_input("Link ao clicar", value=banner.get("link_url", ""), key=f"bn_link_{idx}")
            ativo = c3.checkbox("Ativo", value=bool(banner.get("ativo", True)), key=f"bn_ativo_{idx}")
            editados.append({"imagem_url": imagem_url, "link_url": link_url, "ativo": ativo})

        col_add, col_save = st.columns(2)
        adicionar = col_add.form_submit_button("➕ Adicionar banner")
        salvar = col_save.form_submit_button("💾 Salvar banners")

        if adicionar:
            editados.append({"imagem_url": "", "link_url": "", "ativo": True})
            st.session_state["vitrine_banners_edit"] = editados
            st.rerun()
        if salvar:
            validos = [banner for banner in editados if banner["imagem_url"]]
            storage.salvar_banners(validos)
            st.session_state["vitrine_banners_edit"] = validos or editados
            st.success("Banners salvos.")
            st.rerun()


def view_grupos():
    st_status = whatsapp_client.status()
    conectado = st_status.get("connected", False)

    if st.button("🔄 Atualizar status"):
        st.rerun()

    st.markdown(
        f'<div class="section-title">Status: {ui.status_tag("conectado" if conectado else "desconectado", conectado)}</div>',
        unsafe_allow_html=True,
    )

    if not conectado:
        st.info(
            "Escaneie o QR code abaixo no WhatsApp do número dedicado ao canal: "
            "abra o WhatsApp → Aparelhos conectados → Conectar um aparelho."
        )
        qr = whatsapp_client.qr_disponivel()
        if qr:
            st.image(qr, width=320)
        else:
            st.warning("Aguardando o serviço gerar o QR code... clique em 'Atualizar status' em alguns segundos.")
        return

    st.success("Conectado! Selecione abaixo os grupos que devem receber as ofertas automaticamente.")
    grupos_api = whatsapp_client.listar_grupos()
    salvos = {g["jid"]: g["ativo"] for g in storage.listar_grupos_salvos()}

    if not grupos_api:
        st.info("Nenhum grupo encontrado — confirme que o número dedicado já foi adicionado aos grupos.")
        return

    with st.form("form_grupos"):
        selecionados = []
        for grupo in grupos_api:
            ativo = st.checkbox(
                grupo["name"] or grupo["jid"],
                value=bool(salvos.get(grupo["jid"], False)),
                key=f"grupo_check_{grupo['jid']}",
            )
            selecionados.append({"jid": grupo["jid"], "nome": grupo["name"], "ativo": ativo})
        if st.form_submit_button("💾 Salvar grupos"):
            storage.salvar_grupos(selecionados)
            st.success("Grupos salvos.")
            st.rerun()


def main():
    st.set_page_config(page_title="Painel Vendedor1", page_icon="🛒", layout="wide")
    if not checar_senha():
        return

    ui.inject_css()
    ui.hero("🛒", "Painel Vendedor1", "Repositório de ofertas, configurações e linktree.")

    with st.sidebar:
        pagina = st.radio(
            "Navegação",
            ["📋 Ofertas", "⚙️ Configurações", "🔗 Linktree", "🛍️ Vitrine", "📲 Grupos"],
            index=0,
        )

    cfg = settings.carregar_configuracoes()

    if pagina == "📋 Ofertas":
        view_ofertas(cfg)
    elif pagina == "⚙️ Configurações":
        view_configuracoes(cfg)
    elif pagina == "🔗 Linktree":
        view_linktree()
    elif pagina == "🛍️ Vitrine":
        view_vitrine()
    else:
        view_grupos()


if __name__ == "__main__":
    main()
