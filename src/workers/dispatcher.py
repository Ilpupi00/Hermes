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
        self.pools = {
            "default": ThreadPoolExecutor(max_workers=config.MAX_WORKERS)
        }
        self.worker = get_worker_instance()
        config.logger.info(f"status=dispatcher_ready pools=1 worker_class={config.WORKER_CLASS}")

    def add_pool(self, pool_name: str, max_workers: int):
        if pool_name not in self.pools:
            self.pools[pool_name] = ThreadPoolExecutor(max_workers=max_workers)
            config.logger.info(f"status=pool_created name={pool_name} workers={max_workers}")
            return True
        return False

    def remove_pool(self, pool_name: str):
        """API per la GUI: Elimina un pool e annulla i task in coda."""
        if len(self.pools) <= 1:
            return False, "Impossibile eliminare l'ultimo pool attivo del sistema. Deve esserci almeno un pool per elaborare i task."
            
        if pool_name in self.pools:
            pool = self.pools.pop(pool_name)
            # wait=False non blocca il sistema, cancel_futures=True svuota la coda
            pool.shutdown(wait=False, cancel_futures=True)
            config.logger.warning(f"status=pool_deleted name={pool_name}")
            return True, "Pool eliminato."
        return False, "Pool non trovato."

    def update_pool(self, old_name: str, new_name: str, new_workers: int):
        """API per la GUI: Rinomina e/o ridimensiona i worker dinamicamente."""
        if old_name not in self.pools:
            return False, "Pool non trovato."
        if new_name != old_name and new_name in self.pools:
            return False, "Il nuovo nome è già in uso."

        # Estraiamo il pool
        pool = self.pools.pop(old_name)
        
        # HACK AVANZATO: Modifichiamo la variabile privata del ThreadPoolExecutor
        pool._max_workers = new_workers 
        
        # Lo reinseriamo con il nuovo nome
        self.pools[new_name] = pool
        config.logger.info(f"status=pool_updated old={old_name} new={new_name} workers={new_workers}")
        return True, "Pool aggiornato."

    def submit_chunk(self, chunk, metadata, pool_name="default"):
        # Cerca il pool richiesto, altrimenti fa il fallback su uno disponibile
        pool = self.pools.get(pool_name)
        pool_name_used = pool_name
        if not pool:
            if self.pools:
                first_pool_name = next(iter(self.pools.keys()))
                pool = self.pools[first_pool_name]
                pool_name_used = first_pool_name
            else:
                raise RuntimeError("Nessun thread pool disponibile nel dispatcher.")
        config.logger.info(f"file={metadata['filename']} chunk={metadata['chunk_index']} pool={pool_name_used} status=dispatched rows={len(chunk)}")
        return pool.submit(self.worker.process, chunk, metadata)

    def get_pool_stats(self):
        stats = {}
        for name, pool in self.pools.items():
            coda_attesa = pool._work_queue.qsize()
            stats[name] = {
                "max_workers": pool._max_workers,
                "in_coda": coda_attesa,
                "attivi": "Si" if coda_attesa > 0 else "In attesa"
            }
        return stats

    def shutdown(self):
        for pool in self.pools.values():
            pool.shutdown(wait=True)