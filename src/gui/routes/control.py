import os
import sys
import subprocess
import threading
import time
import datetime as dt
from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import state
from ...core import config
from ... import main as hermes_main
from scheduler import Scheduler

router = APIRouter(prefix="/api")

class StartParams(BaseModel):
    workers: int = Field(..., ge=1)
    interval: int = Field(..., ge=1)

class PoolParams(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    workers: int = Field(..., ge=1)

class UpdatePoolParams(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=64)
    workers: int = Field(..., ge=1)

@router.get("/status")
async def get_status():
    is_running = state.SCHEDULER_THREAD is not None and state.SCHEDULER_THREAD.is_alive()
    pool_stats = {}
    if hermes_main.dispatcher:
        pool_stats = hermes_main.dispatcher.get_pool_stats()

    return {
        "is_running": is_running,
        "pools": pool_stats
    }

@router.post("/pools")
async def create_pool(params: PoolParams):
    if hermes_main.dispatcher:
        success = hermes_main.dispatcher.add_pool(params.name, params.workers)
        return {"success": success}
    return {"success": False, "error": "Hermes offline"}

# --- NUOVE ROTTE PER ELIMINAZIONE E AGGIORNAMENTO ---

@router.delete("/pools/{pool_name}")
async def delete_pool(pool_name: str):
    if hermes_main.dispatcher:
        success, msg = hermes_main.dispatcher.remove_pool(pool_name)
        return {"success": success, "message": msg}
    return {"success": False, "message": "Hermes offline"}

@router.put("/pools/{pool_name}")
async def update_pool(pool_name: str, params: UpdatePoolParams):
    if hermes_main.dispatcher:
        success, msg = hermes_main.dispatcher.update_pool(pool_name, params.new_name, params.workers)
        return {"success": success, "message": msg}
    return {"success": False, "message": "Hermes offline"}

@router.post("/start")
async def start_hermes(params: StartParams):
    if state.SCHEDULER_THREAD and state.SCHEDULER_THREAD.is_alive():
        return {"status": "already_running"}

    # Configura le variabili globali
    config.MAX_WORKERS = params.workers
    config.POLL_INTERVAL = params.interval
    config.init_directories()
    
    hermes_main.keep_running = True
    hermes_main.dispatcher = hermes_main.Dispatcher()
    
    # Funzione che farà girare il macchinario in background
    def run_scheduler():
        sched = Scheduler()
        sched.cyclic(dt.timedelta(seconds=config.POLL_INTERVAL), hermes_main.process_inbox)
        while hermes_main.keep_running:
            sched.exec_jobs()
            time.sleep(1)

    # Lancia Hermes nel thread
    state.SCHEDULER_THREAD = threading.Thread(target=run_scheduler, daemon=True)
    state.SCHEDULER_THREAD.start()
    
    return {"status": "started"}

@router.post("/stop")
async def stop_hermes():
    # Chiude in modo "grazioso" (Graceful Shutdown)
    hermes_main.keep_running = False
    if hermes_main.dispatcher:
        hermes_main.dispatcher.shutdown()
    return {"status": "stopped"}