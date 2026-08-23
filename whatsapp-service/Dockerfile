FROM node:20-slim

# O Baileys depende do libsignal-node via Git — precisamos do git instalado,
# e reescrever URLs git+ssh:// para https:// (o build não tem chave SSH,
# mas o repositório é público, então https funciona sem autenticação).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && git config --global url."https://github.com/".insteadOf "git+ssh://git@github.com/" \
    && git config --global url."https://github.com/".insteadOf "ssh://git@github.com/"

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY . .

CMD ["node", "index.js"]
