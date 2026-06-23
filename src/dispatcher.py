import importlib
from concurrent.futures import ThreadPoolExecutor
from typing import Type
from .worker_base import WorkerBase
from .config import logger, WORKER_CLASS, MAX_WORKERS

def get_worker_instance() -> WorkerBase:
    """Carica dinamicamente la classe worker dal config (HERMES_WORKER_CLASS)."""
    module_name, class_name = WORKER_CLASS.rsplit(".", 1)
    module = importlib.import_module(module_name)
    worker_cls: Type[WorkerBase] = getattr(module, class_name)
    return worker_cls()

class Dispatcher:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self.worker = get_worker_instance()
        logger.info(f"status=dispatcher_ready max_workers={MAX_WORKERS} worker_class={WORKER_CLASS}")

    def submit_chunk(self, chunk, metadata):
        """Sottomette un chunk al pool. Ritorna il Future."""
        logger.info(f"file={metadata['filename']} chunk={metadata['chunk_index']} status=dispatched rows={len(chunk)}")
        return self.executor.submit(self.worker.process, chunk, metadata)

    def shutdown(self):
        self.executor.shutdown(wait=True)