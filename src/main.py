import time
import signal
import argparse
import datetime as dt
import threading
from scheduler import Scheduler
import concurrent.futures

from .core import config
from .core.watcher import get_next_file
from .core.mover import move_file
from .core.reader import read_chunks
from .workers.dispatcher import Dispatcher
from .workers.worker_base import FatalWorkerError
from .api.health import start_health_server
from .db.db import SessionLocal
from .db import repository

keep_running = True
dispatcher = None
file_monitor_pool = concurrent.futures.ThreadPoolExecutor(max_workers=50, thread_name_prefix="FileMonitor")
active_cancel_events = {}  # Mappa: id_esecuzione -> threading.Event

def signal_handler(sig, frame):
    global keep_running
    config.logger.info("status=shutdown_requested draining_pool=True")
    keep_running = False

def parse_cli_args():
    """Definisce e legge gli argomenti passati da riga di comando."""
    parser = argparse.ArgumentParser(description="Hermes - AI Batch Processing Scheduler")
    parser.add_argument("--workers", type=int, help="Sovrascrive HERMES_MAX_WORKERS")
    parser.add_argument("--interval", type=int, help="Sovrascrive HERMES_POLL_INTERVAL")
    parser.add_argument("--port", type=int, default=8080, help="Porta per l'Health Check (default: 8080)")
    return parser.parse_args()

def _process_file_blocking(target_file):
    """Esegue la logica di monitoraggio e chunking di un file in background."""
    config.logger.info(f"file={target_file.name} status=detected")

    # STEP 2 — Atomic Move
    try:
        processing_file = move_file(target_file, config.ARCHIVE)
    except Exception:
        return 

    # STEP 3 & 4 — Chunked Read & Dispatch
    try:
        import re
        job_id_match = re.search(r"job_(\d+)_", processing_file.name)
        job_id = int(job_id_match.group(1)) if job_id_match else None
        
        chunk_futures = []
        cancel_event = threading.Event()
        
        if job_id is not None:
            active_cancel_events[job_id] = cancel_event
            
        # Determiniamo il pool di destinazione recuperando il modello dal DB
        target_pool = "default"
        modello_nome = "default"
        if job_id is not None:
            try:
                with SessionLocal() as db:
                    ctx = repository.get_execution_context(db, job_id)
                    modello_nome = ctx.get("nome_modello", "default")
                    target_pool = dispatcher.get_route(modello_nome)
            except Exception as e:
                config.logger.error(f"status=CIRCUIT_BREAKER file={processing_file.name} reason='Errore DB: Esecuzione {job_id} non trovata. File orfano.'")
                try:
                    move_file(processing_file, config.FAILED)
                except Exception:
                    pass
                return
                
        # Imposta lo stato a "In corso" all'avvio del processing
        if job_id is not None:
            try:
                with SessionLocal() as db:
                    repository.set_task_status_by_execution(db, job_id, "In corso")
                    db.commit()
            except Exception:
                pass

        for idx, chunk in enumerate(read_chunks(processing_file, config.CHUNK_SIZE)):
            metadata = {
                "filename": processing_file.name, 
                "chunk_index": idx,
                "cancel_event": cancel_event,
                "modello": modello_nome
            }
            future = dispatcher.submit_chunk(chunk, metadata, pool_name=target_pool)
            chunk_futures.append(future)
        
        has_fatal_error = False
        
        for future in concurrent.futures.as_completed(chunk_futures):
            try:
                future.result() 
            except FatalWorkerError as fe:
                config.logger.critical(f"status=CIRCUIT_BREAKER file={processing_file.name} reason='{str(fe)}'")
                has_fatal_error = True
                cancel_event.set()
                break 
            except Exception as e:
                config.logger.error(f"Chunk fallito in modo non fatale: {str(e)}")

        if has_fatal_error:
            for f in chunk_futures:
                f.cancel()
            
            # Se stiamo spegnendo Hermes, è una sospensione (Rimandato), non un Fallito vero
            is_shutdown = not keep_running
            new_status = "Rimandato" if is_shutdown else "Fallito"
            target_dir = config.INTERRUPTED if is_shutdown else config.FAILED
            
            if job_id is not None:
                try:
                    with SessionLocal() as db:
                        repository.set_task_status_by_execution(db, job_id, new_status)
                        db.commit()
                except Exception as e:
                    config.logger.error(f"Impossibile aggiornare stato a {new_status} per job {job_id}: {e}")

            move_file(processing_file, target_dir)
            return 

        config.logger.info(f"file={processing_file.name} all_chunks={len(chunk_futures)} status=complete")
        
        # Se tutti i chunk sono andati a buon fine, il task è completato (i worker hanno salvato i risultati)
        if job_id is not None:
            try:
                with SessionLocal() as db:
                    repository.set_task_status_by_execution(db, job_id, "Completato")
                    db.commit()
            except Exception:
                pass

    except Exception as e:
        config.logger.error(f"file={processing_file.name} status=failed_processing error={str(e)}")
        
        is_shutdown = not keep_running
        new_status = "Rimandato" if is_shutdown else "Fallito"
        target_dir = config.INTERRUPTED if is_shutdown else config.FAILED
        
        if 'job_id' in locals() and job_id is not None:
            try:
                with SessionLocal() as db:
                    repository.set_task_status_by_execution(db, job_id, new_status)
                    db.commit()
            except Exception:
                pass
                
        move_file(processing_file, target_dir)
    finally:
        if 'job_id' in locals() and job_id is not None:
            active_cancel_events.pop(job_id, None)

def process_inbox():
    """Il Job che lo scheduler eseguirà ciclicamente."""
    target_file = get_next_file(config.INBOX)
    
    if not target_file:
        return 
        
    # Sottomette l'elaborazione al monitor pool così lo scheduler può subito prelevare altri file
    file_monitor_pool.submit(_process_file_blocking, target_file)

def recover_interrupted_jobs():
    """Recupera i job interrotti (in processing o nella cartella interrupted) e li riporta in INBOX."""
    config.logger.info("status=recovering_jobs from=INTERRUPTED,ARCHIVE to=INBOX")
    
    import shutil
    # Recupera i file in elaborazione (interrotti bruscamente)
    for f in config.ARCHIVE.glob("*.csv"):
        try:
            shutil.move(str(f), str(config.INBOX / f.name))
            config.logger.info(f"status=recovered_from_processing file={f.name}")
        except Exception as e:
            config.logger.error(f"Errore recupero file {f.name}: {e}")
            
    # Recupera i file rimandati (interrotti gracefulmente per shutdown)
    for f in config.INTERRUPTED.glob("*.csv"):
        try:
            shutil.move(str(f), str(config.INBOX / f.name))
            config.logger.info(f"status=recovered_from_interrupted file={f.name}")
        except Exception as e:
            config.logger.error(f"Errore recupero file {f.name}: {e}")

def main():
    global dispatcher
    
    # 1. Parsing argomenti CLI
    args = parse_cli_args()
    
    # Sovrascriviamo le config se passate da terminale (con validazione)
    if args.workers is not None:
        if args.workers < 1:
            raise SystemExit("--workers deve essere >= 1")
        config.MAX_WORKERS = args.workers
    if args.interval is not None:
        if args.interval < 1:
            raise SystemExit("--interval deve essere >= 1")
        config.POLL_INTERVAL = args.interval

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    config.logger.info(f"status=starting hermes_scheduler workers={config.MAX_WORKERS}")
    config.init_directories()
    
    # Riporta in INBOX eventuali job rimasti a metà o falliti prima dell'avvio
    recover_interrupted_jobs()
    
    dispatcher = None
    try:
        # 2. Avvia l'API di Health Check
        health_server = start_health_server(port=args.port)
        
        dispatcher = Dispatcher()
        schedule = Scheduler()
        
        schedule.cyclic(dt.timedelta(seconds=config.POLL_INTERVAL), process_inbox)
        config.logger.info(f"status=scheduler_ready interval={config.POLL_INTERVAL}s")

        while keep_running:
            schedule.exec_jobs()
            time.sleep(1)
    finally:
        config.logger.info("status=shutting_down waiting_for_workers")
        if health_server:
            try:
                config.logger.info("status=shutting_down health_server=True")
                health_server.shutdown()
                health_server.server_close()
            except Exception as e:
                config.logger.error(f"Errore arresto server health: {e}")
        if dispatcher:
            dispatcher.shutdown()
        file_monitor_pool.shutdown(wait=False)
        config.logger.info("status=exit")

if __name__ == "__main__":
    main()
    