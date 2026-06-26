import importlib
from concurrent.futures import ThreadPoolExecutor
from typing import Type
from .worker_base import WorkerBase
from ..core import config

def get_worker_instance() -> WorkerBase:
    """Carica dinamicamente la classe worker dal config."""
    module_name, class_name = config.WORKER_CLASS.rsplit(".", 1)
    module = importlib.import_module(module_name)
    worker_cls: Type[WorkerBase] = getattr(module, class_name)
    return worker_cls()

class Dispatcher:
    def __init__(self):
        # Inizializzato usando config.MAX_WORKERS (valore al momento dello startup)
        self.executor = ThreadPoolExecutor(max_workers=config.MAX_WORKERS)
        self.worker = get_worker_instance()
        config.logger.info(f"status=dispatcher_ready max_workers={config.MAX_WORKERS} worker_class={config.WORKER_CLASS}")

    def submit_chunk(self, chunk, metadata):
        """Sottomette un chunk al pool. Ritorna il Future."""
        config.logger.info(f"file={metadata['filename']} chunk={metadata['chunk_index']} status=dispatched rows={len(chunk)}")
        return self.executor.submit(self.worker.process, chunk, metadata)

    def shutdown(self):
        self.executor.shutdown(wait=True)