import logging
import asyncio
from datetime import datetime

# Stato Globale per la GUI di Hermes
SCHEDULER_THREAD = None
connected_websockets = []
fastapi_loop = None      # Memorizza il loop degli eventi asincroni

# Buffer in memoria dei log con timestamp
log_buffer: list[dict] = []  # [{"timestamp": "2026-06-27T18:00:00", "message": "..."}, ...]
MAX_LOG_BUFFER = 5000         # Limite massimo di righe in memoria

class WsLogHandler(logging.Handler):
    """Intercetta i log testuali e li inoltra ai WebSocket della GUI e li salva in buffer."""
    def emit(self, record):
        now = datetime.now()
        msg = self.format(record)

        # Salva nel buffer con timestamp ISO
        log_buffer.append({
            "timestamp": now.isoformat(timespec="seconds"),
            "message": msg
        })
        # Mantieni il buffer entro il limite (trimming a batch per evitare O(n) ad ogni log)
        if len(log_buffer) > MAX_LOG_BUFFER + 100:
            del log_buffer[:-MAX_LOG_BUFFER]

        if not connected_websockets or not fastapi_loop:
            return

        # Prepara il messaggio con timestamp per il WebSocket
        ws_msg = f"[{now.strftime('%H:%M:%S')}] {msg}"
        for ws in connected_websockets.copy():
            try:
                asyncio.run_coroutine_threadsafe(ws.send_text(ws_msg), fastapi_loop)
            except Exception:
                if ws in connected_websockets:
                    connected_websockets.remove(ws)