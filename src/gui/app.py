import os
import time
import threading
import uvicorn
import logging
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from .routes import (
    auth_router,
    control_router,
    dashboard_router,
    health_router,
    logs_router,
    models_router,
    upload_router,
)
from . import state
from ..core.config import logger # Importiamo il logger globale

# Inizializza FastAPI
app = FastAPI()

# Strumentazione per esportare metriche Prometheus (latenza, status code, traffico, ecc.)
Instrumentator().instrument(app).expose(app)

@app.on_event("startup")
async def startup_event():
    """All'avvio, cattura il loop asincrono e aggancia l'intercettatore di log"""
    state.fastapi_loop = asyncio.get_running_loop()
    
    ws_handler = state.WsLogHandler()
    ws_handler.setFormatter(logging.Formatter('%(message)s'))  # timestamp aggiunto da WsLogHandler
    logger.addHandler(ws_handler)

# Mount dei file statici (CSS, JS)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

app.include_router(dashboard_router)
app.include_router(control_router)
app.include_router(logs_router)
app.include_router(models_router)
app.include_router(upload_router)
app.include_router(auth_router)
app.include_router(health_router)

# --- AVVIO APP IBRIDA ---
def run_fastapi():
    """Avvia il server in un thread separato."""
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="critical")

def main():
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "PyWebView non installato. Installa Hermes con l'extra 'desktop'."
        ) from exc

    t = threading.Thread(target=run_fastapi, daemon=True)
    t.start()
    
    time.sleep(1)
    
    webview.create_window(
        "⚡ Hermes - Control Room", 
        "http://127.0.0.1:8000",
        width=1200, 
        height=800,
        background_color='#111827' 
    )
    webview.start()

if __name__ == "__main__":
    main()
