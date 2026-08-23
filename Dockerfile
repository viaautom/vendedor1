FROM python:3.11-slim

# ffmpeg é usado pelo yt-dlp para juntar áudio+vídeo quando o site serve
# esses streams separados (ex: YouTube em qualidades mais altas).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["streamlit", "run", "dashboard.py", "--server.address=0.0.0.0", "--server.port=8501"]
