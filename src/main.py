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

keep_running = True
dispatcher = None

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

def process_inbox():
    """Il Job che lo scheduler eseguirà ciclicamente."""
    target_file = get_next_file(config.INBOX)
    
    if not target_file:
        return 
        
    config.logger.info(f"file={target_file.name} status=detected")

    # STEP 2 — Atomic Move
    try:
        processing_file = move_file(target_file, config.ARCHIVE)
    except Exception:
        return 

    # STEP 3 & 4 — Chunked Read & Dispatch
    try:
        chunk_futures = []
        cancel_event = threading.Event()
        for idx, chunk in enumerate(read_chunks(processing_file, config.CHUNK_SIZE)):
            metadata = {
                "filename": processing_file.name, 
                "chunk_index": idx,
                "cancel_event": cancel_event
            }
            future = dispatcher.submit_chunk(chunk, metadata)
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
            move_file(processing_file, config.FAILED)
            return 

        config.logger.info(f"file={processing_file.name} all_chunks={len(chunk_futures)} status=complete")

    except Exception as e:
        config.logger.error(f"file={processing_file.name} status=failed_processing error={str(e)}")
        move_file(processing_file, config.FAILED)

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
    
    health_server = None
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
        config.logger.info("status=exit")

if __name__ == "__main__":
    main()