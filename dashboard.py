import base64
import csv
import hashlib
import html
import io
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
import scraper
import settings
import storage
import telegram_poster
import video_tools
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


def buscar_e_persistir(cfg: dict) -> int:
    total_salvas = 0
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
                total_salvas += 1
            ids_vistos = {oferta["id"] for oferta in ofertas}
            storage.marcar_indisponiveis(palavra, fonte, ids_vistos)
    return total_salvas


def id_manual(link: str, nome: str = "") -> str:
    nome = nome or nome_a_partir_do_link(link)
    return storage.gerar_id_curto(nome, link, "M")


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


def formatar_data(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "—"


def render_offer_edit_form(oferta: dict, cfg: dict):
    with st.form(f"form_edit_{oferta['id']}"):
        nome = st.text_input("Nome", value=oferta.get("nome", ""))
        c1, c2 = st.columns(2)
        preco = c1.number_input(
            "Preço (R$)", min_value=0.0, value=float(oferta.get("preco") or 0), step=0.01
        )
        desconto = c2.number_input(
            "Desconto (%)", min_value=0, max_value=100, value=int(oferta.get("desconto_percent") or 0)
        )
        opcoes_nicho = list(cfg["nichos"])
        nicho_atual = oferta.get("keyword") or ""
        if nicho_atual and nicho_atual not in opcoes_nicho:
            opcoes_nicho = [nicho_atual] + opcoes_nicho
        indice = opcoes_nicho.index(nicho_atual) if nicho_atual in opcoes_nicho else 0
        nicho = st.selectbox("Nicho", options=opcoes_nicho or ["geral"], index=indice)
        imagem_url = st.text_input("URL da imagem", value=oferta.get("imagem_url", ""))
        imagem_upload = st.file_uploader(
            "Upload de imagem do produto (opcional)",
            type=["png", "jpg", "jpeg", "webp"],
            help="Faz upload da imagem para usar no cadastro e na vitrine do site.",
        )
        if imagem_upload is not None:
            imagem_url = arquivo_para_data_uri(imagem_upload)
        link = st.text_input("Link", value=oferta.get("link_afiliado", ""))
        destaque = st.checkbox(
            "⭐ Produto em destaque (aparece em destaque no topo da vitrine)",
            value=bool(oferta.get("destaque")),
        )

        col_salvar, col_cancelar = st.columns(2)
        salvar = col_salvar.form_submit_button("💾 Salvar", use_container_width=True)
        cancelar = col_cancelar.form_submit_button("Cancelar", use_container_width=True)
        if salvar:
            storage.atualizar_oferta(
                oferta["id"],
                {
                    "nome": nome,
                    "preco": preco,
                    "desconto_percent": int(desconto),
                    "keyword": nicho,
                    "imagem_url": imagem_url,
                    "link_afiliado": link,
                    "destaque": 1 if destaque else 0,
                },
            )
            del st.session_state["editando_id"]
            st.rerun()
        if cancelar:
            del st.session_state["editando_id"]
            st.rerun()


def render_offer_row(oferta: dict, grupos: list[dict], cfg: dict):
    with st.container(border=True):
        if st.session_state.get("editando_id") == oferta["id"]:
            render_offer_edit_form(oferta, cfg)
            return

        st.session_state.setdefault("selected_ids", [])
        selected_ids = st.session_state["selected_ids"]
        selecionado = oferta["id"] in selected_ids

        col_sel, col_img, col_info, col_tg, col_wa, col_conf, col_grp, col_edit, col_del = st.columns(
            [0.7, 1, 5, 1, 1, 1, 1, 1, 1]
        )
        with col_sel:
            novo_valor = st.checkbox(
                "",
                value=selecionado,
                key=f"sel_{oferta['id']}",
                help=f"Selecionar produto {oferta['id']}",
            )
            if novo_valor and oferta["id"] not in selected_ids:
                selected_ids.append(oferta["id"])
            if not novo_valor and oferta["id"] in selected_ids:
                selected_ids.remove(oferta["id"])
            st.session_state["selected_ids"] = selected_ids

        with col_img:
            st.markdown(ui.thumb_html(oferta.get("imagem_url", "")), unsafe_allow_html=True)
        with col_info:
            estrela = "⭐ " if oferta.get("destaque") else ""
            nome = estrela + html.escape(str(oferta.get("nome", "Oferta")))
            desconto = oferta.get("desconto_percent", 0)
            desconto_txt = f" · -{desconto}%" if desconto else ""
            id_produto = html.escape(str(oferta.get("id", "")))
            st.markdown(
                f'<div class="offer-row-title">{nome}</div>'
                f'<div class="offer-row-meta">🆔 {id_produto} · R$ {float(oferta.get("preco", 0) or 0):.2f}'
                f"{desconto_txt} · 🏷️ {html.escape(str(oferta.get('keyword') or '—'))} · "
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
        with col_tg:
            if st.button("📨", key=f"telegram_{oferta['id']}", use_container_width=True, help="Enviar no Telegram"):
                ok = telegram_poster.postar_oferta(oferta)
                if ok:
                    storage.marcar_enviado(oferta["id"], "telegram")
                    st.rerun()
                else:
                    st.error("Falha ao enviar")
        with col_wa:
            st.link_button("💬", formatar_whatsapp_link(oferta), use_container_width=True, help="Abrir no WhatsApp")
        with col_conf:
            if st.button("✓", key=f"wa_confirma_{oferta['id']}", use_container_width=True, help="Marcar como enviado no WhatsApp"):
                storage.marcar_enviado(oferta["id"], "whatsapp")
                st.rerun()
        with col_grp:
            if grupos:
                if st.button("📲", key=f"grupo_{oferta['id']}", use_container_width=True, help="Enviar aos grupos"):
                    texto = whatsapp_client.formatar_mensagem(oferta)
                    sucesso_algum = any(
                        whatsapp_client.enviar_mensagem(grupo["jid"], texto) for grupo in grupos
                    )
                    if sucesso_algum:
                        storage.marcar_enviado(oferta["id"], "whatsapp_grupo")
                        st.rerun()
                    else:
                        st.error("Falha — confira '📲 Grupos'.")
        with col_edit:
            if st.button("✏️", key=f"edit_{oferta['id']}", use_container_width=True, help="Editar"):
                st.session_state["editando_id"] = oferta["id"]
                st.rerun()
        with col_del:
            if st.button("🗑️", key=f"del_{oferta['id']}", use_container_width=True, help="Remover do repositório"):
                storage.remover_oferta(oferta["id"])
                st.rerun()


def render_offer_list(ofertas: list[dict], cfg: dict):
    grupos = storage.grupos_ativos()
    for oferta in ofertas:
        render_offer_row(oferta, grupos, cfg)


def arquivo_para_data_uri(arquivo) -> str:
    if arquivo is None:
        return ""
    try:
        dados = arquivo.getvalue() or b""
    except Exception:
        return ""
    if not dados:
        return ""
    mime = getattr(arquivo, "type", "") or "image/png"
    return f"data:{mime};base64,{base64.b64encode(dados).decode('ascii')}"


def _preco_valido(valor: str) -> bool:
    try:
        return float(valor.replace(",", ".")) > 0
    except (AttributeError, ValueError):
        return False


def adicionar_links_em_lote(
    links: list[str],
    nicho: str,
    imagens: list = None,
    imagens_urls: list[str] = None,
    precos: list[str] = None,
) -> int:
    adicionadas = 0
    imagens = imagens or []
    imagens_urls = imagens_urls or []
    precos = precos or []
    for indice, link in enumerate(links):
        try:
            dados = scraper.extrair_dados_produto(link)
        except Exception:
            dados = {}
        imagem_upload = arquivo_para_data_uri(imagens[indice]) if indice < len(imagens) else ""
        imagem_url = imagens_urls[indice] if indice < len(imagens_urls) else ""
        try:
            preco_informado = float(precos[indice].replace(",", ".")) if indice < len(precos) and precos[indice] else 0.0
        except ValueError:
            preco_informado = 0.0
        nome_produto = dados.get("nome") or nome_a_partir_do_link(link)
        storage.registrar_oferta(
            {
                "id": id_manual(link, nome_produto),
                "fonte": "Manual",
                "keyword": nicho,
                "nome": nome_produto,
                "preco": preco_informado,
                "desconto_percent": 0,
                "link_afiliado": link,
                "imagem_url": imagem_upload or imagem_url or "",
            }
        )
        adicionadas += 1
    return adicionadas


def view_ofertas(cfg: dict):
    todas = storage.listar_ofertas()
    disponiveis = [o for o in todas if o.get("disponivel")]
    nao_enviados = storage.contagem_nao_enviados()
    enviados_hoje = storage.contagem_enviados_hoje()

    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(ui.stat_card("🔗", "Total de links", len(todas)), unsafe_allow_html=True)
    col2.markdown(ui.stat_card("📭", "Não enviados", nao_enviados), unsafe_allow_html=True)
    col3.markdown(ui.stat_card("🟢", "Disponíveis", len(disponiveis)), unsafe_allow_html=True)
    col4.markdown(ui.stat_card("⏱️", "Intervalo", f"{cfg['check_interval_hours']}h"), unsafe_allow_html=True)

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
    row = st.columns([1, 1])
    with row[0]:
        if st.button("🔎 Buscar ofertas agora", use_container_width=True):
            with st.spinner("Consultando Amazon e Shopee..."):
                total_salvas = buscar_e_persistir(cfg)
            st.session_state["busca_resultado"] = total_salvas
            st.rerun()
    with row[1]:
        if st.button("📨 Testar Telegram", use_container_width=True):
            ok = teste_telegram()
            st.success("Mensagem de teste enviada.") if ok else st.error("Falha no teste do Telegram.")

    with st.expander("➕ Adicionar link(s) — um ou vários, no mesmo nicho"):
        if not cfg["nichos"]:
            st.warning("Cadastre pelo menos um nicho antes de adicionar produtos.")
            if st.button("⚙️ Ir para Configurações e cadastrar um nicho"):
                st.session_state["pagina_atual"] = "⚙️ Configurações"
                st.rerun()
        else:
            st.caption(
                "Cole um link ou vários (um por linha) e escolha o nicho — vale pro "
                "lote inteiro. Informe preço e imagem (URL ou upload) na mesma ordem "
                "dos links. O nome será obtido automaticamente e o desconto pode ser "
                "preenchido depois na edição."
            )
            with st.form("form_manual", clear_on_submit=True):
                links_texto = st.text_area("Link(s) do produto (um por linha) *", height=100)
                nicho_lote = st.selectbox("Nicho (aplicado a todos os links deste lote) *", options=cfg["nichos"])
                precos_texto = st.text_area(
                    "Preço(s) (um por linha, na mesma ordem dos links) *",
                    height=68,
                    placeholder="Ex.: 49,90\n79,90",
                )
                imagens_urls_texto = st.text_area(
                    "URL(s) da imagem (uma por linha, opcional)",
                    height=68,
                    placeholder="Deixe vazio na linha se for enviar um arquivo",
                )
                imagens_upload = st.file_uploader(
                    "Ou envie imagem(ns) (uma por link)",
                    type=["png", "jpg", "jpeg", "webp"],
                    accept_multiple_files=True,
                    help="Se você enviar várias imagens, elas serão usadas na mesma ordem dos links.",
                )
                if st.form_submit_button("Adicionar ao repositório"):
                    links = [linha.strip() for linha in links_texto.split("\n") if linha.strip()]
                    if not links:
                        st.warning("Cole ao menos um link.")
                    else:
                        precos = [linha.strip() for linha in precos_texto.split("\n")]
                        imagens_urls = [linha.strip() for linha in imagens_urls_texto.split("\n")]
                        precos_validos = len(precos) >= len(links) and all(
                            linha and _preco_valido(linha) for linha in precos[: len(links)]
                        )
                        imagens_validas = len(imagens_upload or []) >= len(links) or all(
                            (indice < len(imagens_upload or []) and imagens_upload[indice])
                            or (indice < len(imagens_urls) and imagens_urls[indice])
                            for indice in range(len(links))
                        )
                        if not precos_validos:
                            st.warning("Informe um preço válido para cada link, na mesma ordem.")
                        elif not imagens_validas:
                            st.warning("Informe uma URL ou envie uma imagem para cada link.")
                        else:
                            with st.spinner(f"Buscando dados de {len(links)} link(s)..."):
                                adicionadas = adicionar_links_em_lote(
                                    links,
                                    nicho_lote,
                                    imagens_upload or [],
                                    imagens_urls,
                                    precos,
                                )
                            st.success(f"{adicionadas} oferta(s) adicionada(s) ao nicho '{nicho_lote}'.")
                            st.rerun()

    st.markdown('<div class="section-title">Ofertas no repositório</div>', unsafe_allow_html=True)
    col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
    with col_f1:
        nicho_filtro = st.selectbox("Filtrar por nicho", options=["Todos"] + cfg["nichos"])
    with col_f2:
        mostrar_todas = st.toggle("Mostrar esgotados", value=True)
    with col_f3:
        busca_texto = st.text_input("Buscar por nome")

    st.session_state.setdefault("selected_ids", [])
    selected_ids = st.session_state["selected_ids"]
    if selected_ids:
        ids_formatados = "#" + "-".join(selected_ids)
        st.caption("IDs selecionados")
        st.code(ids_formatados, language="text")
        st.caption("Use o ícone de copiar no bloco acima para copiar os IDs.")
        if st.button("Limpar seleção", use_container_width=True):
            st.session_state["selected_ids"] = []
            st.rerun()

    ofertas = todas if mostrar_todas else disponiveis
    if nicho_filtro != "Todos":
        ofertas = [o for o in ofertas if o.get("keyword") == nicho_filtro]
    if busca_texto:
        termo = busca_texto.strip().lower()
        ofertas = [o for o in ofertas if termo in (o.get("nome") or "").lower()]

    if ofertas:
        st.caption(f"{len(ofertas)} oferta(s)")
        render_offer_list(ofertas, cfg)
    else:
        st.info("Nenhuma oferta encontrada com esses filtros.")


def view_configuracoes(cfg: dict):
    st.markdown('<div class="section-title">Filtros e busca</div>', unsafe_allow_html=True)
    with st.form("form_config"):
        keywords_texto = st.text_area(
            "Palavras-chave de busca (uma por linha) — usadas na busca automática Shopee/Amazon",
            value="\n".join(cfg["keywords"]),
            height=120,
        )
        nichos_texto = st.text_area(
            "Nichos (uma por linha) — usados pra categorizar ofertas na vitrine e no cadastro manual",
            value="\n".join(cfg["nichos"]),
            height=120,
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
                "nichos": [linha.strip() for linha in nichos_texto.split("\n") if linha.strip()],
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


def view_leads_acessos():
    resumo = storage.resumo_leads_acessos()
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(ui.stat_card("👥", "Leads totais", resumo["total_leads"]), unsafe_allow_html=True)
    col2.markdown(ui.stat_card("👁️", "Acessos totais", resumo["total_acessos"]), unsafe_allow_html=True)
    col3.markdown(ui.stat_card("📥", "Leads hoje", resumo["leads_hoje"]), unsafe_allow_html=True)
    col4.markdown(ui.stat_card("📈", "Acessos hoje", resumo["acessos_hoje"]), unsafe_allow_html=True)

    st.markdown('<div class="section-title">Acessos nos últimos 14 dias</div>', unsafe_allow_html=True)
    acessos = storage.acessos_por_dia()
    if acessos:
        import pandas as pd
        grafico = pd.DataFrame(acessos).pivot_table(
            index="dia", columns="pagina", values="total", aggfunc="sum", fill_value=0
        )
        st.line_chart(grafico)
    else:
        st.info("Ainda não há acessos registrados nas páginas públicas.")

    st.markdown('<div class="section-title">Leads captados</div>', unsafe_allow_html=True)
    leads = storage.listar_leads()
    if not leads:
        st.info("Nenhum lead captado ainda.")
        return
    dados_csv = io.StringIO()
    campos = ["nome", "email", "whatsapp", "origem", "criado_em"]
    escritor = csv.DictWriter(dados_csv, fieldnames=campos)
    escritor.writeheader()
    escritor.writerows({campo: lead.get(campo, "") for campo in campos} for lead in leads)
    st.download_button("⬇️ Exportar leads CSV", dados_csv.getvalue(), "leads.csv", "text/csv", use_container_width=True)
    st.dataframe(
        [{"Nome": lead["nome"], "E-mail": lead["email"], "WhatsApp": lead.get("whatsapp", ""), "Origem": lead.get("origem", ""), "Cadastrado em": formatar_data(lead["criado_em"])} for lead in leads],
        use_container_width=True,
        hide_index=True,
    )


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
    st.caption("Aparecem no topo de /site, antes das ofertas. Use uma URL ou envie uma imagem.")

    banners_salvos = storage.listar_banners()
    if "vitrine_banners_edit" not in st.session_state:
        st.session_state["vitrine_banners_edit"] = banners_salvos or [
            {"imagem_url": "", "link_url": "", "ativo": True}
        ]

    with st.form("form_vitrine_banners"):
        editados = []
        for idx, banner in enumerate(st.session_state["vitrine_banners_edit"]):
            c1, c2, c3 = st.columns([4, 4, 1])
            imagem_salva = banner.get("imagem_url", "")
            url_inicial = "" if imagem_salva.startswith("data:image/") else imagem_salva
            imagem_url = c1.text_input("URL da imagem", value=url_inicial, key=f"bn_img_{idx}")
            imagem_upload = c1.file_uploader(
                "Ou envie uma imagem",
                type=["png", "jpg", "jpeg", "webp"],
                key=f"bn_upload_{idx}",
            )
            imagem = arquivo_para_data_uri(imagem_upload) or imagem_url or imagem_salva
            link_url = c2.text_input("Link ao clicar", value=banner.get("link_url", ""), key=f"bn_link_{idx}")
            ativo = c3.checkbox("Ativo", value=bool(banner.get("ativo", True)), key=f"bn_ativo_{idx}")
            editados.append({"imagem_url": imagem, "link_url": link_url, "ativo": ativo})

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


def view_video():
    st.markdown('<div class="section-title">Baixar vídeo por link</div>', unsafe_allow_html=True)
    st.caption(
        "Cole o link de um vídeo público e baixe o arquivo pra usar nas suas "
        "divulgações. Baixe só conteúdo que você tem direito de usar (seu "
        "próprio, licenciado, ou de sites/vídeos que permitem download)."
    )
    url = st.text_input("Link do vídeo")
    if st.button("⬇️ Baixar"):
        if not url:
            st.warning("Cole um link primeiro.")
        else:
            with st.spinner("Baixando... pode levar alguns segundos, dependendo do tamanho."):
                try:
                    dados, nome = video_tools.baixar_video(url)
                    st.session_state["video_baixado"] = (dados, nome)
                    st.success(f"Pronto: {nome} ({len(dados) / 1024 / 1024:.1f} MB)")
                except Exception as exc:
                    st.error(f"Falha ao baixar: {exc}")

    if "video_baixado" in st.session_state:
        dados, nome = st.session_state["video_baixado"]
        col1, col2 = st.columns([3, 1])
        with col1:
            st.download_button(
                "💾 Salvar vídeo no computador",
                data=dados,
                file_name=nome,
                mime=video_tools.mime_de(nome),
                use_container_width=True,
            )
        with col2:
            if st.button("🗑️ Limpar", use_container_width=True):
                del st.session_state["video_baixado"]
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


PAGINAS = ["📋 Ofertas", "👥 Leads e acessos", "⚙️ Configurações", "🔗 Linktree", "🛍️ Vitrine", "📲 Grupos", "⬇️ Vídeo"]


def main():
    st.set_page_config(page_title="Painel Vendedor1", page_icon="🛒", layout="wide")
    if not checar_senha():
        return

    ui.inject_css()
    ui.hero("🛒", "Painel Vendedor1", "Repositório de ofertas, configurações e linktree.")

    if "pagina_atual" not in st.session_state:
        st.session_state["pagina_atual"] = PAGINAS[0]

    cols = st.columns(len(PAGINAS))
    for col, nome_pagina in zip(cols, PAGINAS):
        ativo = st.session_state["pagina_atual"] == nome_pagina
        if col.button(
            nome_pagina,
            use_container_width=True,
            type="primary" if ativo else "secondary",
            key=f"nav_{nome_pagina}",
        ):
            st.session_state["pagina_atual"] = nome_pagina
            st.rerun()

    st.write("")
    cfg = settings.carregar_configuracoes()
    pagina = st.session_state["pagina_atual"]

    if pagina == "📋 Ofertas":
        view_ofertas(cfg)
    elif pagina == "👥 Leads e acessos":
        view_leads_acessos()
    elif pagina == "⚙️ Configurações":
        view_configuracoes(cfg)
    elif pagina == "🔗 Linktree":
        view_linktree()
    elif pagina == "🛍️ Vitrine":
        view_vitrine()
    elif pagina == "📲 Grupos":
        view_grupos()
    else:
        view_video()


if __name__ == "__main__":
    main()
