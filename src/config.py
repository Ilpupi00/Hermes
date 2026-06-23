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


WORKER_CLASS = os.getenv("HERMES_WORKER_CLASS","hermes.worker.DefaultWorker")