import time
import sys
import signal
import schedule
from . import config
from .watcher import get_next_file
from .mover import move_file
from .reader import read_chunks
from .dispatcher import Dispatcher

keep_running = True
dispatcher = None

def signal_handler(sig, frame):
    global keep_running
    config.logger.info("status=shutdown_requested draining_pool=True")
    keep_running = False

def process_inbox():
    """Il 'Job' che lo scheduler eseguirà ad ogni intervallo."""
    target_file = get_next_file(config.INBOX)
    
    if not target_file:
        return # Nessun file, esce e aspetta il prossimo giro
        
    config.logger.info(f"file={target_file.name} status=detected")

    # STEP 2 — Atomic Move
    try:
        processing_file = move_file(target_file, config.ARCHIVE)
    except Exception:
        return # Riproverà al prossimo ciclo

    # STEP 3 & 4 — Chunked Read & Dispatch
    try:
        chunk_futures = []
        for idx, chunk in enumerate(read_chunks(processing_file, config.CHUNK_SIZE)):
            metadata = {
                "filename": processing_file.name,
                "chunk_index": idx,
            }
            future = dispatcher.submit_chunk(chunk, metadata)
            chunk_futures.append(future)
        
        # Attendiamo che tutti i chunk del file siano finiti
        for f in chunk_futures:
            f.result() # Solleva eventuali eccezioni
            
        config.logger.info(f"file={processing_file.name} all_chunks={len(chunk_futures)} status=complete")

    except Exception as e:
        config.logger.error(f"file={processing_file.name} status=failed_processing error={str(e)}")
        move_file(processing_file, config.FAILED)

def main():
    global dispatcher
    
    # Setup graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    config.logger.info("status=starting hermes_scheduler")
    config.init_directories()
    
    dispatcher = Dispatcher()

    # 1. Configura lo scheduler usando la variabile d'ambiente
    schedule.every(config.POLL_INTERVAL).seconds.do(process_inbox)
    config.logger.info(f"status=scheduler_ready interval={config.POLL_INTERVAL}s")

    # 2. Loop principale pulito
    try:
        while keep_running:
            schedule.run_pending()
            time.sleep(60) # Sleep di base per non sforzare la CPU

    finally:
        config.logger.info("status=shutting_down waiting_for_workers")
        if dispatcher:
            dispatcher.shutdown()
        config.logger.info("status=exit")

if __name__ == "__main__":
    main()