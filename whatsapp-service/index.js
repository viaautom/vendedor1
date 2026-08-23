"use strict";

const express = require("express");
const pino = require("pino");
const QRCode = require("qrcode");
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
} = require("@whiskeysockets/baileys");

const AUTH_DIR = process.env.AUTH_DIR || "./auth_info";
const TOKEN = process.env.WHATSAPP_SERVICE_TOKEN || "";
const PORT = process.env.PORT || 3000;
const ENVIO_INTERVALO_MS = parseInt(process.env.ENVIO_INTERVALO_MS || "3000", 10);

const logger = pino({ level: "info" });

let sock = null;
let conectado = false;
let qrAtual = null;

async function conectar() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  sock = makeWASocket({
    auth: state,
    logger: pino({ level: "silent" }),
    printQRInTerminal: false,
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      try {
        qrAtual = await QRCode.toBuffer(qr, { type: "png", width: 320 });
      } catch (err) {
        logger.error({ err }, "Falha ao gerar QR code");
      }
    }

    if (connection === "open") {
      conectado = true;
      qrAtual = null;
      logger.info("WhatsApp conectado.");
    }

    if (connection === "close") {
      conectado = false;
      const statusCode = lastDisconnect && lastDisconnect.error && lastDisconnect.error.output
        ? lastDisconnect.error.output.statusCode
        : undefined;
      const deveReconectar = statusCode !== DisconnectReason.loggedOut;
      logger.warn({ statusCode, deveReconectar }, "Conexão com o WhatsApp fechada.");
      if (deveReconectar) {
        setTimeout(conectar, 3000);
      } else {
        logger.error(
          "Sessão deslogada pelo celular — apague o volume de auth_info e escaneie o QR novamente."
        );
      }
    }
  });
}

// Fila simples que espaça os envios (evita rajada de mensagens).
const filaEnvio = [];
let processandoFila = false;

function enfileirarEnvio(jid, mensagem) {
  return new Promise((resolve, reject) => {
    filaEnvio.push({ jid, mensagem, resolve, reject });
    processarFila();
  });
}

async function processarFila() {
  if (processandoFila) return;
  processandoFila = true;
  while (filaEnvio.length > 0) {
    const item = filaEnvio.shift();
    try {
      if (!sock || !conectado) {
        throw new Error("WhatsApp não conectado");
      }
      await sock.sendMessage(item.jid, { text: item.mensagem });
      item.resolve(true);
    } catch (err) {
      item.reject(err);
    }
    if (filaEnvio.length > 0) {
      await new Promise((resolve) => setTimeout(resolve, ENVIO_INTERVALO_MS));
    }
  }
  processandoFila = false;
}

const app = express();
app.use(express.json());

function checarToken(req, res, next) {
  if (TOKEN && req.header("X-Internal-Token") !== TOKEN) {
    res.status(401).json({ error: "token inválido" });
    return;
  }
  next();
}

app.get("/status", checarToken, (req, res) => {
  res.json({ connected: conectado });
});

app.get("/qr", checarToken, (req, res) => {
  if (!qrAtual) {
    res.status(404).json({ error: "sem qr pendente (já conectado ou aguardando geração)" });
    return;
  }
  res.type("png").send(qrAtual);
});

app.get("/groups", checarToken, async (req, res) => {
  if (!sock || !conectado) {
    res.status(503).json({ error: "não conectado" });
    return;
  }
  try {
    const grupos = await sock.groupFetchAllParticipating();
    const lista = Object.values(grupos).map((g) => ({ jid: g.id, name: g.subject }));
    res.json(lista);
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.post("/send", checarToken, async (req, res) => {
  const { jid, message } = req.body || {};
  if (!jid || !message) {
    res.status(400).json({ error: "jid e message são obrigatórios" });
    return;
  }
  try {
    await enfileirarEnvio(jid, message);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

app.listen(PORT, "0.0.0.0", () => {
  logger.info(`whatsapp-service ouvindo na porta ${PORT}`);
});

conectar().catch((err) => {
  logger.error({ err }, "Falha ao iniciar conexão com o WhatsApp");
});
