# SmarTel — Telegram Business Managed AI Bot
#
#   docker build -t smartel .
#   docker run -d --name smartel --env-file .env -v "$PWD/storage:/app/storage" smartel
#
# The owner claim code is printed to stdout, so it shows up in `docker logs`.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so source edits don't invalidate the layer cache.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runtime data (SQLite DB, uploads) lives in a volume; drop privileges.
RUN mkdir -p storage/uploads storage/vector_store \
    && useradd --create-home --shell /usr/sbin/nologin smartel \
    && chown -R smartel:smartel /app \
    && chmod 0755 /app/docker-entrypoint.sh

# The entrypoint starts as root only to fix ownership of the mounted storage
# volume (Railway mounts volumes as root), then drops to the `smartel` user.
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Persistent data (SQLite DB, uploads) lives in /app/storage. On Railway, attach a
# Railway Volume mounted at /app/storage (Dockerfile VOLUME is not supported).

CMD ["python", "main.py"]
