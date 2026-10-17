"""Font and answer cloud search service (Google Drive & Telegram cloud)."""
import glob
import io
import logging
import os
import zipfile
from typing import Any

log = logging.getLogger("smartel.fonts")

def list_cloud_fonts() -> list[dict[str, Any]]:
    """Scan available cloud font archives in google_drive and extract font metadata."""
    fonts = []
    # Index zip archives in google_drive/
    for zpath in glob.glob("google_drive/*.zip") + glob.glob("google_drive/**/*.zip", recursive=True):
        try:
            with zipfile.ZipFile(zpath, "r") as z:
                for info in z.infolist():
                    name = info.filename
                    base = os.path.basename(name)
                    if base.startswith("._") or "__MACOSX" in name:
                        continue
                    if base.lower().endswith((".ttf", ".otf", ".woff", ".woff2")):
                        fonts.append({
                            "source": "google_drive",
                            "archive": zpath,
                            "entry": name,
                            "name": base,
                            "size": info.file_size,
                        })
        except Exception as e:
            log.warning("error scanning zip file %s: %s", zpath, e)

    # Also include standalone font files in google_drive/
    for fpath in glob.glob("google_drive/*.ttf") + glob.glob("google_drive/*.otf"):
        base = os.path.basename(fpath)
        if not base.startswith("._"):
            try:
                fonts.append({
                    "source": "google_drive",
                    "file_path": fpath,
                    "name": base,
                    "size": os.path.getsize(fpath),
                })
            except Exception:
                pass
    return fonts


def search_fonts(query: str) -> list[dict[str, Any]]:
    """Search for fonts matching query string."""
    q = (query or "").strip().lower()
    all_fonts = list_cloud_fonts()
    if not q:
        return all_fonts[:10]
    return [f for f in all_fonts if q in f["name"].lower()][:10]


def get_font_content(font_meta: dict[str, Any]) -> tuple[str, bytes] | None:
    """Retrieve the raw font binary bytes and filename from archive or cloud file."""
    try:
        if "archive" in font_meta and "entry" in font_meta:
            with zipfile.ZipFile(font_meta["archive"], "r") as z:
                data = z.read(font_meta["entry"])
                return font_meta["name"], data
        elif "file_path" in font_meta:
            with open(font_meta["file_path"], "rb") as f:
                return font_meta["name"], f.read()
    except Exception as e:
        log.error("failed reading font content: %s", e)
    return None
