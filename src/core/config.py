import os
import logging
from dotenv import load_dotenv
from pathlib import Path

#Caricamento del file .env
load_dotenv()

#Configurazione del Log
logging.basicConfig(
    level=logging.INFO,
    format='[HERMES] %(message)s'
)

logger= logging.getLogger("hermes")

# Directory del ciclo di vita. Devono condividere lo stesso filesystem affinché
# i rename usati per pubblicazione e claim siano realmente atomici.
DATA_ROOT = Path(os.getenv("HERMES_DATA_ROOT", "."))
INBOX = Path(os.getenv("HERMES_INBOX", str(DATA_ROOT / "uploads_web")))
PROCESSING = Path(os.getenv("HERMES_PROCESSING", str(DATA_ROOT / "processing")))
ARCHIVE = Path(os.getenv("HERMES_ARCHIVE", str(DATA_ROOT / "processed")))
FAILED = Path(os.getenv("HERMES_FAILED", str(DATA_ROOT / "failed")))
INTERRUPTED = Path(
    os.getenv("HERMES_INTERRUPTED", str(DATA_ROOT / "interrupted"))
)

POLL_INTERVAL = int(os.getenv("HERMES_POLL_INTERVAL", "60"))
CHUNK_SIZE = int(os.getenv("HERMES_CHUNK_SIZE", "1000"))
MAX_WORKERS = int(os.getenv("HERMES_MAX_WORKERS", "4"))
MAX_RETRIES = int(os.getenv("HERMES_MAX_RETRIES", "3"))
ORPHAN_GRACE_SECONDS = max(
    0, int(os.getenv("HERMES_ORPHAN_GRACE_SECONDS", "300"))
)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = os.getenv("DB_PORT", "5432")

# --- AI LOCALE (vLLM / Ollama) ---
LOCAL_AI_BASE_URL = os.getenv("HERMES_AI_BASE_URL", "http://localhost:8000/v1")

# --- HUGGINGFACE ---
# HF_TOKEN è il nome canonico. HUGGING_FACE resta temporaneamente supportato
# per non rompere le configurazioni create prima della baseline.
HF_TOKEN = os.getenv("HF_TOKEN", os.getenv("HUGGING_FACE", "")).strip().strip('"')
HF_INFERENCE_PROVIDER = (
    os.getenv("HF_INFERENCE_PROVIDER", "featherless-ai").strip()
    or "featherless-ai"
)

# PATH AGGIORNATO ALLA NUOVA STRUTTURA
WORKER_CLASS = os.getenv("HERMES_WORKER_CLASS", "src.workers.hybrid_worker.HybridWorker")


def init_directories():
    for directory in [INBOX, PROCESSING, ARCHIVE, FAILED, INTERRUPTED]:
        directory.mkdir(parents=True,exist_ok=True)
