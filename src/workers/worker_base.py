from abc import ABC, abstractmethod
import pandas as pd

class FatalWorkerError(Exception):
    """Eccezione sollevata per errori irreversibili del worker (es. token non valido)."""
    pass

class WorkerBase(ABC):
    @abstractmethod
    def process(self, chunk: pd.DataFrame, metadata: dict) -> dict:
        """Elabora un chunk del CSV."""
        pass