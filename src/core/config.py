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

#Variabili di ambiente
INBOX = Path(os.getenv("HERMES_INBOX", "./uploads_web"))
ARCHIVE = Path(os.getenv("HERMES_ARCHIVE", "./processed"))
FAILED = Path(os.getenv("HERMES_FAILED", "./failed"))

POLL_INTERVAL = int(os.getenv("HERMES_POLL_INTERVAL", "60"))
CHUNK_SIZE = int(os.getenv("HERMES_CHUNK_SIZE", "1000"))
MAX_WORKERS = int(os.getenv("HERMES_MAX_WORKERS", "4"))
MAX_RETRIES = int(os.getenv("HERMES_MAX_RETRIES", "3"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password") # Modificato per chiarezza
DB_PORT = os.getenv("DB_PORT", "5432")

# --- AI LOCALE (vLLM / Ollama) ---
LOCAL_AI_BASE_URL = os.getenv("HERMES_AI_BASE_URL", "http://localhost:8000/v1")

# PATH AGGIORNATO ALLA NUOVA STRUTTURA
WORKER_CLASS = os.getenv("HERMES_WORKER_CLASS", "src.workers.ai_worker.LocalAIWorker")

def init_directories():
    for directory in [INBOX, ARCHIVE, FAILED]:
        directory.mkdir(parents=True,exist_ok=True)