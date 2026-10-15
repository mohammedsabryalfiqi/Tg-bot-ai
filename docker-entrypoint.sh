#!/bin/sh
# Container entrypoint.
#
# Hosted platforms (e.g. Railway) mount volumes owned by root, but the app runs
# as the unprivileged `smartel` user. Without this step SQLite cannot create
# /app/storage/smartel.db and the bot crashes on startup. So: if we start as
# root, fix ownership of the storage directories and drop privileges before
# running the app. If we are already non-root, just run the app.
set -e

STORAGE_DIR="${SMARTEL_STORAGE_DIR:-/app/storage}"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$STORAGE_DIR/uploads" "$STORAGE_DIR/vector_store"
    chown -R smartel:smartel "$STORAGE_DIR"
    exec runuser -u smartel -- "$@"
fi

exec "$@"
