# Buscador de Ofertas — Fitness & Bem-Estar

Script que busca ofertas na Shopee e na Amazon para um conjunto de
palavras-chave, filtra pelo desconto mínimo configurado e posta
automaticamente as novas ofertas no seu canal do Telegram.

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

Abrir o painel (Streamlit):
```bash
streamlit run dashboard.py
```

Alternativa: usar `cron` (Linux/Mac) para rodar `python main.py` a cada
X horas, sem precisar do `--loop`:
```
0 */6 * * * cd /caminho/do/projeto && venv/bin/python main.py >> log.txt 2>&1
```

## 3.1 Página pública (linktree)

Edite os links reais (Telegram, WhatsApp, Instagram, TikTok, site) em
[public/linktree/index.html](public/linktree/index.html) antes de publicar —
é um HTML estático simples, sem build.

## 4. Deploy

O projeto vem com `Dockerfile` e `docker-compose.yml`, definindo três
serviços a partir da mesma imagem (exceto `web`):

- `web`: Nginx servindo a página pública (linktree) em `public/linktree/`.
- `dashboard`: o painel administrativo (Streamlit), na porta 8501 — protegido
  por senha (`ADMIN_PASSWORD` no `.env`).
- `worker`: roda `python main.py --loop` continuamente, buscando e postando
  ofertas novas no Telegram.

`dashboard` e `worker` compartilham um volume (`ofertas_data`) com o banco
de deduplicação.

**Sempre defina `ADMIN_PASSWORD` no `.env` antes de publicar** — sem ela o
painel fica aberto para qualquer pessoa que tiver a URL.

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
5. Deploy. O Dokploy vai buildar a imagem e subir os três serviços
   (`web`, `dashboard`, `worker`).
6. Configure os **Domains** (um por serviço exposto — `worker` não precisa
   de domínio, ele não serve HTTP):
   - `web` → porta `80` → domínio da linktree pública.
   - `dashboard` → porta `8501` → domínio/subdomínio do painel.
   - Ative HTTPS (Let's Encrypt) em cada domínio.

   Enquanto você não tem domínio próprio, dá pra usar o
   [sslip.io](https://sslip.io) (resolve `algo.SEU-IP.sslip.io` para o
   próprio IP do servidor, sem precisar configurar DNS):
   - Linktree: `vendedor1.SEU-IP.sslip.io`
   - Painel: `admin.vendedor1.SEU-IP.sslip.io`

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

Edite a lista `KEYWORDS` em `config.py` para trocar os termos buscados,
e `MIN_DISCOUNT_PERCENT` / `MIN_PRICE` / `MAX_PRICE` para ajustar os
filtros de oferta.

## 6. Sobre postar no WhatsApp

Este MVP posta apenas no Telegram, que tem API de bot aberta e
gratuita. Para postar automaticamente no WhatsApp de forma oficial e
sem risco de banimento, é necessário usar a **WhatsApp Business
Platform (Cloud API)**, que exige cadastro de negócio verificado e
tem custo por mensagem em alguns casos. Não recomendamos automatizar
postagem em grupos comuns do WhatsApp, pois isso não é suportado
oficialmente pela plataforma.

## 7. Estrutura do projeto

```
vendedor1/
├── config.py              # configurações e variáveis de ambiente
├── storage.py             # controle de deduplicação (SQLite)
├── telegram_poster.py     # formata e posta no Telegram
├── main.py                # orquestrador / scheduler
├── dashboard.py           # painel administrativo (Streamlit)
├── clients/
│   ├── shopee_client.py   # busca ofertas na Shopee
│   ├── amazon_client.py   # busca ofertas na Amazon
│   └── mercadolivre_client.py  # busca ofertas no Mercado Livre
├── public/linktree/       # página pública de links
├── deploy/                # exemplo de configuração Nginx
├── Dockerfile, docker-compose.yml, .dockerignore
├── requirements.txt
└── .env.example
```
