import pandas as pd
from pathlib import Path
from typing import Iterator
from .config import logger

def read_chunks(filepath: Path, chunk_size: int) -> Iterator[pd.DataFrame]:
    """Generatore che legge un file CSV a chunk usando pandas."""
    try:
        # engine='c' è il default, molto veloce
        for chunk in pd.read_csv(filepath, chunksize=chunk_size):
            yield chunk
    except Exception as e:
        logger.error(f"file={filepath.name} status=parse_error error={str(e)}")
        raise e