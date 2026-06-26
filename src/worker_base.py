from abc import ABC, abstractmethod
import pandas as pd

class WorkerBase(ABC):
    @abstractmethod
    def process(self, chunk: pd.DataFrame, metadata: dict) -> dict:
        """Elabora un chunk del CSV."""
        pass