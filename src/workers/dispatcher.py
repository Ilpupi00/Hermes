import importlib
import threading
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
        self.lock = threading.RLock()
        self.pools = {
            "default": ThreadPoolExecutor(max_workers=config.MAX_WORKERS)
        }
        self.worker = get_worker_instance()
        config.logger.info(f"status=dispatcher_ready pools=1 worker_class={config.WORKER_CLASS}")
        self.routing_table = {} 
        self.worker = get_worker_instance()
        self.pool_active_tasks = {"default": 0}

    def add_pool(self, pool_name: str, max_workers: int):
        if max_workers < 1:
            config.logger.warning(
                f"status=pool_create_rejected name={pool_name} workers={max_workers} reason=invalid_worker_count"
            )
            return False
        with self.lock:
            if pool_name not in self.pools:
                self.pools[pool_name] = ThreadPoolExecutor(max_workers=max_workers)
                self.pool_active_tasks[pool_name] = 0
                config.logger.info(f"status=pool_created name={pool_name} workers={max_workers}")
                return True
        return False

    def remove_pool(self, pool_name: str):
        """API per la GUI: Elimina un pool e annulla i task in coda."""
        with self.lock:
            if len(self.pools) <= 1:
                return False, "Impossibile eliminare l'ultimo pool attivo del sistema. Deve esserci almeno un pool per elaborare i task."
                
            if pool_name in self.pools:
                pool = self.pools.pop(pool_name)
                self.pool_active_tasks.pop(pool_name, None)
                # wait=False non blocca il sistema, cancel_futures=True svuota la coda
                pool.shutdown(wait=False, cancel_futures=True)
                config.logger.warning(f"status=pool_deleted name={pool_name}")
                return True, "Pool eliminato."
            return False, "Pool non trovato."

    def update_pool(self, old_name: str, new_name: str, new_workers: int):
        """API per la GUI: Rinomina e/o ridimensiona i worker dinamicamente."""
        if new_workers < 1:
            return False, "Il numero di worker deve essere >= 1."
        
        with self.lock:
            if old_name not in self.pools:
                return False, "Pool non trovato."
            if new_name != old_name and new_name in self.pools:
                return False, "Il nuovo nome è già in uso."

            # Estraiamo il pool
            pool = self.pools.pop(old_name)
            current_workers = getattr(pool, "_max_workers", None)
            
            # ThreadPoolExecutor non espone un resize pubblico: se cambia la size, creiamo un nuovo pool.
            if current_workers == new_workers:
                self.pools[new_name] = pool
                self.pool_active_tasks[new_name] = self.pool_active_tasks.pop(old_name, 0)
            else:
                new_pool = ThreadPoolExecutor(max_workers=new_workers)
                self.pools[new_name] = new_pool
                self.pool_active_tasks[new_name] = 0  # i task vecchi resteranno sul vecchio pool
                # Non cancelliamo i task già in coda sul vecchio pool; verranno completati.
                pool.shutdown(wait=False, cancel_futures=False)
                
            config.logger.info(f"status=pool_updated old={old_name} new={new_name} workers={new_workers}")
            return True, "Pool aggiornato."

    def submit_chunk(self, chunk, metadata, pool_name="default"):
        with self.lock:
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
        
        with self.lock:
            if pool_name_used not in self.pool_active_tasks:
                self.pool_active_tasks[pool_name_used] = 0
            self.pool_active_tasks[pool_name_used] += 1

        future = pool.submit(self.worker.process, chunk, metadata)

        def on_done(f):
            with self.lock:
                if pool_name_used in self.pool_active_tasks:
                    self.pool_active_tasks[pool_name_used] = max(0, self.pool_active_tasks[pool_name_used] - 1)

        future.add_done_callback(on_done)
        return future

    def get_pool_stats(self):
        stats = {}
        with self.lock:
            for name, pool in self.pools.items():
                coda_attesa = pool._work_queue.qsize()
                active_tot = self.pool_active_tasks.get(name, 0)
                in_esecuzione = max(0, active_tot - coda_attesa)
                
                stats[name] = {
                    "max_workers": pool._max_workers,
                    "in_coda": coda_attesa,
                    "in_esecuzione": in_esecuzione,
                    "attivi": "Si" if active_tot > 0 else "In attesa"
                }
        return stats

    def set_route(self, model_name: str, pool_name: str):
        """API per la GUI: Associa un modello a un ThreadPool specifico."""
        with self.lock:
            # Se il pool non esiste, fallback al default
            if pool_name not in self.pools:
                pool_name = "default"
            self.routing_table[model_name] = pool_name
            config.logger.info(f"status=route_updated model={model_name} target_pool={pool_name}")
            return True

    def delete_route(self, model_name: str):
        """API per la GUI: Rimuove la regola di routing per un dato modello."""
        with self.lock:
            if model_name in self.routing_table:
                del self.routing_table[model_name]
                config.logger.info(f"status=route_deleted model={model_name}")
                return True
            return False

    def get_routes(self):
        """Restituisce una copia della routing table corrente."""
        with self.lock:
            return dict(self.routing_table)

    def get_route(self, model_name: str) -> str:
        """Restituisce il pool corretto per un dato modello."""
        with self.lock:
            return self.routing_table.get(model_name, "default")

    def shutdown(self):
        with self.lock:
            pools_copy = list(self.pools.values())
        for pool in pools_copy:
            pool.shutdown(wait=True)