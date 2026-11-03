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
from .core.job_file import parse_job_filename
from .core.reconciliation import reconcile_jobs
from .core.reader import read_chunks
from .workers.dispatcher import Dispatcher
from .workers.worker_base import FatalWorkerError, WorkerCancelledError
from .api.health import start_health_server
from .db.db import SessionLocal
from .db import repository
from .db.status import JobStatus

keep_running = True
dispatcher = None
file_monitor_pool = concurrent.futures.ThreadPoolExecutor(max_workers=50, thread_name_prefix="FileMonitor")
active_cancel_events = {}  # Mappa: id_esecuzione -> threading.Event
requested_cancellations = set()
shutdown_interruptions = set()
_cancellation_lock = threading.RLock()


def request_job_cancellation(job_id: int) -> bool:
    """Registra l'annullamento e segnala l'eventuale job già attivo."""
    with _cancellation_lock:
        requested_cancellations.add(job_id)
        cancel_event = active_cancel_events.get(job_id)
        if cancel_event is not None:
            cancel_event.set()
            return True
        return False


def clear_job_cancellation(job_id: int) -> None:
    with _cancellation_lock:
        requested_cancellations.discard(job_id)


def is_job_cancellation_requested(job_id: int) -> bool:
    with _cancellation_lock:
        return job_id in requested_cancellations


def is_job_shutdown_interruption(job_id: int) -> bool:
    with _cancellation_lock:
        return job_id in shutdown_interruptions


def interrupt_active_jobs() -> int:
    """Interrompe i worker attivi senza trasformare lo stop in annullamento."""
    with _cancellation_lock:
        active = list(active_cancel_events.items())
        shutdown_interruptions.update(job_id for job_id, _ in active)
    for _, cancel_event in active:
        cancel_event.set()
    return len(active)


def _register_active_job(job_id: int) -> threading.Event:
    cancel_event = threading.Event()
    with _cancellation_lock:
        active_cancel_events[job_id] = cancel_event
        if job_id in requested_cancellations:
            cancel_event.set()
        elif not keep_running:
            shutdown_interruptions.add(job_id)
            cancel_event.set()
    return cancel_event


def _unregister_active_job(job_id: int) -> None:
    with _cancellation_lock:
        active_cancel_events.pop(job_id, None)
        requested_cancellations.discard(job_id)
        shutdown_interruptions.discard(job_id)

def signal_handler(sig, frame):
    global keep_running
    config.logger.info("status=shutdown_requested draining_pool=True")
    keep_running = False
    interrupt_active_jobs()

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

    # Il rename INBOX -> PROCESSING assegna il file a una sola istanza Hermes.
    try:
        processing_file = move_file(target_file, config.PROCESSING)
    except Exception:
        return 

    # STEP 3 & 4 — Chunked Read & Dispatch
    try:
        try:
            job_file_ids = parse_job_filename(processing_file.name)
        except ValueError as error:
            config.logger.error(
                f"status=invalid_filename file={processing_file.name} reason='{error}'"
            )
            move_file(processing_file, config.FAILED)
            return
        job_id = job_file_ids.execution_id
        
        chunk_futures = []
        cancel_event = _register_active_job(job_id)

        if cancel_event.is_set():
            is_cancelled = is_job_cancellation_requested(job_id)
            new_status = (
                JobStatus.CANCELLED.value
                if is_cancelled
                else JobStatus.DEFERRED.value
            )
            target_dir = config.CANCELLED if is_cancelled else config.INTERRUPTED
            with SessionLocal() as db:
                repository.set_task_status_by_execution(
                    db, job_id, new_status
                )
                db.commit()
            move_file(processing_file, target_dir)
            config.logger.info(
                f"job={job_id} status={new_status} before_dispatch=True"
            )
            return
            
        # Determiniamo il pool di destinazione recuperando il modello dal DB
        target_pool = "default"
        modello_nome = "default"
        chunk_size = config.CHUNK_SIZE
        if job_id is not None:
            try:
                with SessionLocal() as db:
                    ctx = repository.get_execution_context(db, job_id)
                    modello_nome = ctx.get("nome_modello", "default")
                    chunk_size = ctx.get("chunk_size", config.CHUNK_SIZE)
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
                    repository.set_task_status_by_execution(
                        db, job_id, JobStatus.RUNNING.value
                    )
                    db.commit()
            except Exception:
                pass

        config.logger.info(
            f"file={processing_file.name} chunk_size={chunk_size} "
            "status=chunking_started"
        )
        for idx, chunk in enumerate(read_chunks(processing_file, chunk_size)):
            metadata = {
                "filename": processing_file.name, 
                "chunk_index": idx,
                "cancel_event": cancel_event,
                "modello": modello_nome
            }
            future = dispatcher.submit_chunk(chunk, metadata, pool_name=target_pool)
            chunk_futures.append(future)
        
        has_fatal_error = False
        was_interrupted = False
        has_row_errors = False
        
        for future in concurrent.futures.as_completed(chunk_futures):
            try:
                chunk_result = future.result()
                if (
                    isinstance(chunk_result, dict)
                    and chunk_result.get("error_rows", 0) > 0
                ):
                    has_row_errors = True
            except WorkerCancelledError as error:
                config.logger.info(
                    f"file={processing_file.name} status=interrupted "
                    f"reason='{str(error)}'"
                )
                was_interrupted = True
                cancel_event.set()
                break
            except FatalWorkerError as fe:
                config.logger.critical(f"status=CIRCUIT_BREAKER file={processing_file.name} reason='{str(fe)}'")
                has_fatal_error = True
                cancel_event.set()
                break 
            except Exception as e:
                config.logger.error(f"Chunk fallito: {str(e)}")
                has_fatal_error = True
                cancel_event.set()
                break

        if is_job_cancellation_requested(job_id):
            was_interrupted = True

        if has_fatal_error or was_interrupted:
            for f in chunk_futures:
                f.cancel()

            # Un annullamento utente è terminale; lo stop del motore è recuperabile.
            is_cancelled = is_job_cancellation_requested(job_id)
            is_shutdown = is_job_shutdown_interruption(job_id) or not keep_running
            if is_cancelled:
                new_status = JobStatus.CANCELLED.value
                target_dir = config.CANCELLED
            elif is_shutdown:
                new_status = JobStatus.DEFERRED.value
                target_dir = config.INTERRUPTED
            else:
                new_status = JobStatus.FAILED.value
                target_dir = config.FAILED
            
            if job_id is not None:
                try:
                    with SessionLocal() as db:
                        repository.set_task_status_by_execution(db, job_id, new_status)
                        db.commit()
                except Exception as e:
                    config.logger.error(f"Impossibile aggiornare stato a {new_status} per job {job_id}: {e}")

            move_file(processing_file, target_dir)
            return 

        if has_row_errors:
            config.logger.error(
                f"file={processing_file.name} status=failed_with_row_errors"
            )
            if job_id is not None:
                try:
                    with SessionLocal() as db:
                        repository.set_task_status_by_execution(
                            db, job_id, JobStatus.FAILED.value
                        )
                        db.commit()
                except Exception as e:
                    config.logger.error(
                        f"Impossibile aggiornare stato a {JobStatus.FAILED.value} "
                        f"per job {job_id}: {e}"
                    )
            move_file(processing_file, config.FAILED)
            return

        config.logger.info(f"file={processing_file.name} all_chunks={len(chunk_futures)} status=complete")
        
        # Se tutti i chunk sono andati a buon fine, il task è completato (i worker hanno salvato i risultati)
        if job_id is not None:
            try:
                with SessionLocal() as db:
                    repository.set_task_status_by_execution(
                        db, job_id, JobStatus.COMPLETED.value
                    )
                    db.commit()
            except Exception:
                pass

        move_file(processing_file, config.ARCHIVE)

    except Exception as e:
        config.logger.error(f"file={processing_file.name} status=failed_processing error={str(e)}")
        
        is_cancelled = (
            'job_id' in locals()
            and job_id is not None
            and is_job_cancellation_requested(job_id)
        )
        is_shutdown = (
            ('job_id' in locals() and is_job_shutdown_interruption(job_id))
            or not keep_running
        )
        if is_cancelled:
            new_status = JobStatus.CANCELLED.value
            target_dir = config.CANCELLED
        elif is_shutdown:
            new_status = JobStatus.DEFERRED.value
            target_dir = config.INTERRUPTED
        else:
            new_status = JobStatus.FAILED.value
            target_dir = config.FAILED
        
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
            _unregister_active_job(job_id)

def process_inbox():
    """Il Job che lo scheduler eseguirà ciclicamente."""
    target_file = get_next_file(config.INBOX)

    if not target_file:
        return 
        
    # Sottomette l'elaborazione al monitor pool così lo scheduler può subito prelevare altri file
    file_monitor_pool.submit(_process_file_blocking, target_file)

def recover_interrupted_jobs():
    """Alias temporaneo mantenuto per compatibilità con integrazioni esistenti."""
    return reconcile_jobs()

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
    
    # Riconcilia record e file prima di accettare nuovi job.
    reconcile_jobs()
    
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
