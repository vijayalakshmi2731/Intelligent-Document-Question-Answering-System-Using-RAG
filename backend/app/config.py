import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _load_env(path):
    """Minimal .env loader (KEY=VALUE lines); real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env(BASE_DIR / ".env")
DATA_DIR = Path(os.getenv("DOCQA_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "docqa.sqlite3"
FRONTEND_DIR = BASE_DIR / "frontend"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".html", ".htm"}
MAX_UPLOAD_MB = int(os.getenv("DOCQA_MAX_UPLOAD_MB", "25"))

DEFAULT_CHUNK_SIZE = 800      # characters
DEFAULT_CHUNK_OVERLAP = 150
TOP_K = int(os.getenv("DOCQA_TOP_K", "5"))
# below this top-1 cosine similarity the system declines to answer
MIN_RELEVANCE = float(os.getenv("DOCQA_MIN_RELEVANCE", "0.12"))
# answer sentences below this similarity to the context count as unsupported
SUPPORT_THRESHOLD = float(os.getenv("DOCQA_SUPPORT_THRESHOLD", "0.2"))

TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # optional, for compatible gateways
LLM_MODEL = os.getenv("DOCQA_LLM_MODEL", "gpt-4o-mini")
EMBEDDING_BACKEND = os.getenv("DOCQA_EMBEDDING_BACKEND", "hash")  # hash | st
ST_MODEL = os.getenv("DOCQA_ST_MODEL", "all-MiniLM-L6-v2")

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
