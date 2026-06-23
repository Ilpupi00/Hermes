import pandas as pd
import time
from .worker_base import WorkerBase
from .config import logger

class DefaultWorker(WorkerBase):
    def process(self, chunk: pd.DataFrame, metadata: dict) -> dict:
        """
        Worker Stub: Simula l'elaborazione del chunk loggando e dormendo un po'.
        Nella Fase 2, questo chiamerà l'AI API.
        """
        filename = metadata.get("filename")
        chunk_idx = metadata.get("chunk_index")
        
        # Simula tempo di rete/AI
        time.sleep(1)
        
        logger.info(f"file={filename} chunk={chunk_idx} status=processed_stub rows={len(chunk)}")
        
        return {"status": "ok", **metadata}