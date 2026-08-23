# Buscador de Ofertas — Fitness & Bem-Estar

Sistema que busca ofertas na Shopee e na Amazon (ou aceita adição manual)
para um conjunto de palavras-chave, mantém um repositório persistente de
ofertas, posta as novas automaticamente no Telegram, e expõe três telas:
um painel administrativo, uma vitrine pública das ofertas disponíveis e
uma página de links (linktree) — tudo editável pelo próprio painel, sem
precisar mexer em código.

## 1. Instalação

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Preencha o `.env` com suas credenciais reais (veja abaixo como
conseguir cada uma).

## 2. Como conseguir as credenciais

### Telegram
1. Abra o Telegram e fale com **@BotFather**.
2. Envie `/newbot`, siga as instruções e copie o **token** gerado → `TELEGRAM_BOT_TOKEN`.
3. Adicione o bot como **administrador** do seu canal.
4. `TELEGRAM_CHANNEL_ID` pode ser o username do canal (`@seucanal`) ou o ID numérico.

### Shopee Affiliate
1. Cadastre-se no **Portal de Afiliados da Shopee**.
2. Na área de API/Open Platform, gere seu `Partner ID` e `Partner Key`.
3. ⚠️ A Shopee atualiza esse painel com frequência — confira a documentação
   oficial atual antes de rodar em produção, pois o formato de assinatura
   pode mudar.

### Amazon Associados (PA API)
1. Tenha uma conta de **Associados Amazon Brasil** aprovada.
2. Gere as chaves de acesso na área de API.
3. Preencha `AMAZON_ACCESS_KEY`, `AMAZON_SECRET_KEY` e `AMAZON_PARTNER_TAG`.
4. ⚠️ A Amazon exige vendas qualificadas recentes para manter a API ativa.

## 3. Rodando localmente

Rodar uma vez (bom para testar):
```bash
python main.py
```

Rodar continuamente, verificando a cada `CHECK_INTERVAL_HOURS`:
```bash
python main.py --loop
```

Abrir o painel administrativo (Streamlit):
```bash
streamlit run dashboard.py
```

Abrir a vitrine pública (ofertas disponíveis) e a linktree:
```bash
streamlit run loja.py --server.port 8502
streamlit run linktree.py --server.port 8503
```

Alternativa: usar `cron` (Linux/Mac) para rodar `python main.py` a cada
X horas, sem precisar do `--loop`:
```
0 */6 * * * cd /caminho/do/projeto && venv/bin/python main.py >> log.txt 2>&1
```

## 3.1 Painel administrativo

Ao abrir o painel (`dashboard.py`), a tela inicial é sempre **"📋 Ofertas"**:
lista o repositório inteiro de ofertas já encontradas (link, nome, preço,
nicho, data/hora da última busca), sem repetir produto, com indicadores de
Telegram/WhatsApp (cinza = não enviado, colorido = já enviado por aquele
canal). Ali também dá pra colar manualmente o link de um produto (útil
enquanto a Shopee/Amazon ainda não estão conectadas) — ele entra no mesmo
repositório e passa a aparecer na vitrine pública e nos botões de envio,
igual a uma oferta encontrada automaticamente.

As outras telas do painel (barra lateral):
- **⚙️ Configurações**: keywords, desconto mínimo, preço mínimo (com opção
  "não se aplica"), preço máximo e intervalo de busca do worker — tudo
  editável ali, sem precisar mexer em `.env` nem redeployar.
- **🔗 Linktree**: título, subtítulo, cor primária/fundo, logo (upload de
  imagem ou emoji) e a lista de links — o que você salva ali aparece
  imediatamente na página pública da linktree.
- **🛍️ Vitrine**: título/subtítulo de `/site` e banners promocionais
  (imagem + link) exibidos no topo da vitrine pública.
- **📲 Grupos**: pareamento e seleção dos grupos de WhatsApp que recebem as
  ofertas automaticamente (veja seção 6).
- **⬇️ Vídeo**: cola um link de vídeo público e baixa o arquivo (via
  `yt-dlp`) pra usar nas divulgações — baixe só conteúdo que você tem
  direito de usar.

## 4. Deploy

O projeto vem com `Dockerfile` (Python) + `whatsapp-service/Dockerfile`
(Node.js) e `docker-compose.yml`, definindo cinco serviços:

- `linktree`: página pública de links (porta 8503).
- `loja`: vitrine pública das ofertas disponíveis, agrupadas por nicho
  (porta 8502, roda com `--server.baseUrlPath=site`).
- `dashboard`: o painel administrativo, na porta 8501 — protegido por senha
  (`ADMIN_PASSWORD` no `.env`).
- `worker`: roda `python main.py --loop` continuamente, buscando e postando
  ofertas novas no Telegram e nos grupos de WhatsApp configurados (relê as
  configurações do painel a cada ciclo).
- `whatsapp`: serviço Node.js (Baileys) que mantém a sessão do WhatsApp e
  envia as mensagens pros grupos — **sem domínio público**, só acessível
  pelos outros serviços na rede interna do compose.

`linktree`, `loja`, `dashboard` e `worker` compartilham um volume
(`ofertas_data`) com o banco SQLite — o repositório único de ofertas,
configurações e links da linktree. O `whatsapp` tem seu próprio volume
(`whatsapp_auth`) com a sessão pareada, separado do resto.

**Sempre defina `ADMIN_PASSWORD` e `WHATSAPP_SERVICE_TOKEN` no `.env` antes
de publicar** — sem o primeiro, o painel fica aberto pra qualquer um; sem
o segundo, o serviço do WhatsApp fica sem proteção mesmo estando na rede
interna.

### 4.1 Deploy com Dokploy (recomendado)

O projeto está preparado para deploy via [Dokploy](https://dokploy.com)
(PaaS self-hosted com Traefik, que já cuida de proxy e HTTPS automático).

1. **Suba o código para um repositório Git** (GitHub/GitLab/Gitea) — o
   Dokploy faz o build a partir do repositório.
2. No Dokploy, dentro do projeto → **Create Service → Compose**.
3. Conecte o repositório Git, branch `main`, e aponte para o
   `docker-compose.yml` da raiz do projeto.
4. Em **Environment**, cole o conteúdo do seu `.env` (as mesmas variáveis
   de `.env.example`, com os valores reais — não esqueça o
   `ADMIN_PASSWORD`).
5. Deploy. O Dokploy vai buildar as imagens e subir os cinco serviços
   (`linktree`, `loja`, `dashboard`, `worker`, `whatsapp`) — o `whatsapp`
   não precisa de domínio, é só interno.
6. Configure os **Domains** (`worker` não precisa de domínio, não serve HTTP):
   - `linktree` → porta `8503` → domínio raiz, path `/`.
   - `loja` → porta `8502` → **mesmo domínio raiz**, path `/site` (o
     Dokploy permite mais de um domínio com o mesmo Host e Path diferente,
     cada um apontando pra um serviço).
   - `dashboard` → porta `8501` → domínio/subdomínio separado do painel.
   - Ative HTTPS (Let's Encrypt) em cada domínio.

   Enquanto você não tem domínio próprio, dá pra usar o
   [sslip.io](https://sslip.io) (resolve `algo.SEU-IP.sslip.io` para o
   próprio IP do servidor, sem precisar configurar DNS). Exemplo real deste
   projeto:
   - Linktree: `https://vendedor1.SEU-IP.sslip.io/`
   - Vitrine: `https://vendedor1.SEU-IP.sslip.io/site`
   - Painel: `https://admin.vendedor1.SEU-IP.sslip.io`

   Quando tiver um domínio de verdade, é só trocar o domínio em cada
   serviço no Dokploy e apontar o DNS — sem precisar mexer no código.

### 4.2 Deploy manual (VPS sem Dokploy)

```bash
# 1. Copie o projeto para o servidor e preencha o .env
cp .env.example .env
nano .env   # não esqueça o ADMIN_PASSWORD

# 2. Suba os containers
docker compose up -d --build

# 3. Configure o Nginx — veja deploy/nginx.conf.example
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/vendedor1
sudo nano /etc/nginx/sites-available/vendedor1   # ajuste os domínios e o caminho do projeto
sudo ln -s /etc/nginx/sites-available/vendedor1 /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 4. HTTPS
sudo certbot --nginx -d seudominio.com.br -d admin.seudominio.com.br
```

Importante: não abra a porta 8501 no firewall do VPS — o acesso ao painel
deve passar sempre pelo Nginx (com HTTPS). Libere só as portas 80 e 443
(`sudo ufw allow 80,443/tcp`).

## 5. Ajustando o nicho

Keywords e filtros de preço/desconto agora são editados direto na aba
**⚙️ Configurações** do painel (veja seção 3.1) — não precisa mais editar
`config.py` nem redeployar. `config.py` só define os valores iniciais
(usados na primeira vez, antes de qualquer configuração ser salva).

## 6. Postando automaticamente em grupos do WhatsApp

O envio automático para grupos usa o **[Baileys](https://github.com/WhiskeySockets/Baileys)**,
uma biblioteca que implementa o protocolo do WhatsApp Web (não é a API
oficial da Meta/WhatsApp Business Platform — que exige cadastro de negócio
verificado e tem custo por mensagem). O Baileys simula um cliente web
normal, então usa um número de WhatsApp de verdade.

### 6.1 Pareamento (só uma vez)

1. Suba os containers (`docker compose up -d --build` ou via Dokploy).
2. Abra o painel → **📲 Grupos**. Vai aparecer um QR code (ele demora
   alguns segundos pra ser gerado — clique em "🔄 Atualizar status" se
   ainda não aparecer).
3. No **número dedicado ao canal** (recomendado: não usar um número
   pessoal), abra WhatsApp → **Aparelhos conectados** → **Conectar um
   aparelho** → escaneie o QR.
4. Depois de conectado, a sessão fica salva no volume `whatsapp_auth` —
   não precisa escanear de novo, a não ser que desconecte pelo celular ou
   fique muito tempo offline.
5. Ainda em **📲 Grupos**, com o status "conectado", marque quais grupos
   (dentre os que esse número já participa) devem receber as ofertas
   automaticamente e clique em **Salvar grupos**.

### 6.2 Como funciona depois de pareado

- O worker manda toda oferta nova pros grupos marcados como ativos, do
  mesmo jeito que já faz com o Telegram.
- No painel, cada oferta também tem um botão **"📲 Enviar aos grupos"**
  pra reenviar manualmente.
- O ícone 📲 no card fica cinza (não enviado) ou colorido (já enviado
  àquela oferta).

### 6.3 Cuidados (evitar banimento do número)

- Use um número **dedicado**, não o principal de ninguém.
- O número precisa **já estar dentro do grupo** antes de poder postar nele
  — o sistema não entra/sai de grupos sozinho.
- O `whatsapp-service` já espaça os envios automaticamente (alguns
  segundos entre mensagens, mesmo mandando pra vários grupos de uma vez) —
  não desative isso reduzindo `ENVIO_INTERVALO_MS` demais.
- Evite trocar de grupo com muita frequência e evite volumes muito altos
  num intervalo curto — ajuste `CHECK_INTERVAL_HOURS` (aba Configurações)
  com folga.

## 7. Estrutura do projeto

```
vendedor1/
├── config.py              # credenciais/infra (só via .env — tokens, senha do admin)
├── settings.py            # configurações de negócio editáveis (keywords, filtros, intervalo)
├── storage.py             # repositório de ofertas, config, links e grupos (SQLite)
├── ui_common.py           # CSS/design system e helpers de card compartilhados
├── telegram_poster.py     # formata e posta no Telegram
├── whatsapp_client.py     # cliente HTTP pro whatsapp-service (grupos)
├── main.py                # worker / loop de busca
├── dashboard.py           # painel administrativo (Streamlit)
├── loja.py                # vitrine pública das ofertas disponíveis (Streamlit)
├── linktree.py            # página pública de links (Streamlit)
├── clients/
│   ├── shopee_client.py   # busca ofertas na Shopee
│   ├── amazon_client.py   # busca ofertas na Amazon
│   └── mercadolivre_client.py  # busca ofertas no Mercado Livre (não usado no fluxo ainda)
├── whatsapp-service/      # microserviço Node.js (Baileys) — sessão + envio a grupos
│   ├── index.js
│   ├── package.json
│   └── Dockerfile
├── deploy/                # exemplo de configuração Nginx (deploy manual, sem Dokploy)
├── Dockerfile, docker-compose.yml, .dockerignore
├── requirements.txt
└── .env.example
```
