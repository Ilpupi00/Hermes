import os
from pathlib import Path
from typing import Optional
# pyrefly: ignore [missing-import]
from .config import logger

def get_next_file(inbox_path: Path)-> Optional[Path]:
    """Restituisce il file .csv più vecchio nella cartella inbox."""
    try:
        files = []
        for entry in os.scandir(inbox_path):
            if entry.is_file() and entry.name.endswith(".csv"):
                files.append(entry)
        if not files:
            return None
        files.sort(key=lambda x: x.stat().st_mtime)

        return Path(files[0].path)
    
    except Exception as e:
        logger.error(f"status=watcher_error error={str(e)}")
        return None
