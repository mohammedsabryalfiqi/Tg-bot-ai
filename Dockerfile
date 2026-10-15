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
    && chown -R smartel:smartel /app
USER smartel

VOLUME ["/app/storage"]

CMD ["python", "main.py"]
