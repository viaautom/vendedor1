"""
Download de vídeo por link (via yt-dlp), usado na aba "⬇️ Vídeo" do painel.

Uso responsável: baixe apenas conteúdo que você tem direito de usar (seu
próprio conteúdo, material licenciado, ou de plataformas/vídeos que
permitem download).
"""
import mimetypes
import os
import tempfile

import yt_dlp

TAMANHO_MAXIMO_MB = 500


def baixar_video(url: str) -> tuple[bytes, str]:
    """Baixa o vídeo do link informado e retorna (bytes, nome_do_arquivo).
    Levanta exceção se falhar (link inválido, vídeo indisponível, etc.)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        opcoes = {
            "outtmpl": os.path.join(tmpdir, "%(title).100s.%(ext)s"),
            "format": f"best[ext=mp4][filesize<{TAMANHO_MAXIMO_MB}M]/best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "restrictfilenames": True,
        }
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url, download=True)
            caminho = ydl.prepare_filename(info)

        if not os.path.exists(caminho):
            # o pós-processamento (merge de áudio/vídeo) pode trocar a extensão
            base = os.path.splitext(os.path.basename(caminho))[0]
            candidatos = [f for f in os.listdir(tmpdir) if f.startswith(base)]
            if not candidatos:
                raise FileNotFoundError("O download terminou mas o arquivo não foi encontrado.")
            caminho = os.path.join(tmpdir, candidatos[0])

        with open(caminho, "rb") as arquivo:
            dados = arquivo.read()
        return dados, os.path.basename(caminho)


def mime_de(nome_arquivo: str) -> str:
    tipo, _ = mimetypes.guess_type(nome_arquivo)
    return tipo or "application/octet-stream"
