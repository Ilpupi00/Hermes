from fastapi import APIRouter, WebSocket, Query
from fastapi.responses import PlainTextResponse
from datetime import datetime
from .. import state

router = APIRouter()

@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    state.connected_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # Mantiene la connessione viva
    except:
        if websocket in state.connected_websockets:
            state.connected_websockets.remove(websocket)


@router.get("/api/logs/download")
async def download_logs(
    start: str = Query(None, description="Data inizio ISO (es. 2026-06-27T00:00:00)"),
    end: str = Query(None, description="Data fine ISO (es. 2026-06-27T23:59:59)")
):
    """Scarica i log in formato .txt, con filtro opzionale per data."""
    entries = state.log_buffer

    # Filtra per intervallo di date se specificato
    try:
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None
    except ValueError:
        start_dt = end_dt = None

    filtered = []
    for entry in entries:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if start_dt and ts < start_dt:
                continue
            if end_dt and ts > end_dt:
                continue
        except Exception:
            pass
        filtered.append(f"[{entry['timestamp']}] {entry['message']}")

    if not filtered:
        content = "Nessun log trovato per il periodo selezionato."
    else:
        header = "=" * 60 + "\n"
        header += f"  HERMES — Log Export\n"
        header += f"  Generato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        if start_dt or end_dt:
            header += f"  Filtro: {start or 'inizio'} → {end or 'adesso'}\n"
        header += f"  Righe totali: {len(filtered)}\n"
        header += "=" * 60 + "\n\n"
        content = header + "\n".join(filtered)

    filename = f"hermes_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
