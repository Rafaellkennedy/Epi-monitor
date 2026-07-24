# =========================================================
# Dockerfile - EPI Monitor (CFTV & AI Vision Monitoring)
# =========================================================
FROM python:3.12-slim

# Impede a criação de arquivos .pyc e força unbuffered I/O
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Instala pacotes do sistema operacional exigidos pelo OpenCV, Qt, FFmpeg e PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libqt5widgets5 \
    netcat-openbsd \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia e instala as dependências Python
COPY epi_monitor/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código-fonte da aplicação
COPY epi_monitor/ ./epi_monitor/

# Copia e configura o script de inicialização
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Diretório de trabalho na execução do app Python
WORKDIR /app/epi_monitor

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "app.main"]
