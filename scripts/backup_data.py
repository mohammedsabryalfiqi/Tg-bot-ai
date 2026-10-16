#!/usr/bin/env python3
"""Create a consistent, timestamped backup of Alfiqi Ai runtime data.

Example (run on the host, before deploying):
    python3 scripts/backup_data.py --storage ./storage --output ./backups

All SQLite databases (including one per delegated admin) are copied through
SQLite's online backup API. Uploads and vector-store files are added to the ZIP.
The .env file is intentionally excluded; keep it separately and securely.
"""
from __future__ import annotations

import argparse
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def _backup_sqlite(source: Path, target: Path) -> bool:
    try:
        with sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True, timeout=15) as src:
            with sqlite3.connect(target) as dst:
                src.backup(dst)
        return True
    except sqlite3.DatabaseError:
        return False


def create_backup(storage: Path, output_dir: Path) -> Path:
    storage = storage.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not storage.is_dir():
        raise FileNotFoundError(f"Storage directory not found: {storage}")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = output_dir / f"alfiqi-ai-backup-{stamp}.zip"
    with tempfile.TemporaryDirectory(prefix="alfiqi-backup-") as temp:
        temp_dir = Path(temp)
        db_copies: list[tuple[Path, Path]] = []
        for source in sorted(storage.glob("*")):
            if source.is_file() and (source.suffix in {".db", ".sqlite", ".sqlite3"}):
                target = temp_dir / source.name
                if _backup_sqlite(source, target):
                    db_copies.append((target, source.relative_to(storage)))
        if not db_copies:
            raise RuntimeError(f"No SQLite databases found in {storage}; refusing to create an empty backup")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for copy, relative in db_copies:
                zf.write(copy, relative.as_posix())
            for folder in ("uploads", "vector_store"):
                source_dir = storage / folder
                if source_dir.is_dir():
                    for source in source_dir.rglob("*"):
                        if source.is_file():
                            zf.write(source, source.relative_to(storage).as_posix())
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path("storage"),
                        help="runtime data directory (default: ./storage)")
    parser.add_argument("--output", type=Path, default=Path("backups"),
                        help="backup destination, preferably outside the deployment volume")
    args = parser.parse_args()
    backup = create_backup(args.storage, args.output)
    print(f"Backup created: {backup}")
    print("Keep a secure copy of .env / SMARTEL_FERNET_KEY separately to decrypt saved API keys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
