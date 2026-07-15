import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
MEDIA_INBOX_DIR = Path(os.environ.get("MEDIA_INBOX_DIR", "/media/inbox"))
MEDIA_LIBRARY_ROOT = Path(os.environ.get("MEDIA_LIBRARY_ROOT", "/media/library"))
MEDIA_MANUAL_REVIEW_DIR = Path(os.environ.get("MEDIA_MANUAL_REVIEW_DIR", "/media/manual_review"))

DB_PATH = DATA_DIR / "library.db"
COVERS_DIR = DATA_DIR / "covers"

DEFAULT_PATH_TEMPLATE = "{category}/{subject}/{author}/{series}/{title}"

ADMIN_PORT = int(os.environ.get("ADMIN_PORT", "8001"))
PUBLIC_PORT = int(os.environ.get("PUBLIC_PORT", "8000"))

SUPPORTED_EPUB_EXTENSIONS = (".epub",)


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_INBOX_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    MEDIA_MANUAL_REVIEW_DIR.mkdir(parents=True, exist_ok=True)
