"""
Test unitari per src/gui/routes/logs.py

Usa FastAPI TestClient per testare le route HTTP senza avviare un vero server.
Copre:
- GET /api/logs/download: nessun log, con log, filtro start/end, parametri non validi
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from src.gui.routes.logs import router
import src.gui.state as state


# ---------------------------------------------------------------------------
# Fixture: app FastAPI di test + reset buffer
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_buffer():
    state.log_buffer.clear()
    yield
    state.log_buffer.clear()


def _add_log(message: str, ts: datetime = None):
    """Helper: aggiunge una voce al buffer."""
    ts = ts or datetime.now()
    state.log_buffer.append({
        "timestamp": ts.isoformat(timespec="seconds"),
        "message": message,
    })


# ---------------------------------------------------------------------------
# Test: GET /api/logs/download
# ---------------------------------------------------------------------------

class TestDownloadLogs:
    def test_empty_buffer_returns_200(self, client):
        """Anche senza log deve restituire 200."""
        r = client.get("/api/logs/download")
        assert r.status_code == 200

    def test_empty_buffer_message(self, client):
        """Con buffer vuoto deve comunicare che non ci sono log."""
        r = client.get("/api/logs/download")
        assert "Nessun log" in r.text

    def test_logs_present_in_response(self, client):
        """I messaggi nel buffer devono comparire nella risposta."""
        _add_log("avvio hermes")
        r = client.get("/api/logs/download")
        assert "avvio hermes" in r.text

    def test_response_has_header_with_row_count(self, client):
        """La risposta deve contenere la riga 'Righe totali'."""
        _add_log("msg1")
        _add_log("msg2")
        r = client.get("/api/logs/download")
        assert "Righe totali" in r.text

    def test_content_disposition_header(self, client):
        """Deve impostare Content-Disposition con il filename corretto."""
        _add_log("log")
        r = client.get("/api/logs/download")
        assert "attachment" in r.headers.get("content-disposition", "")
        assert "hermes_logs_" in r.headers.get("content-disposition", "")

    def test_filter_start_excludes_old_logs(self, client):
        """Il filtro 'start' deve escludere i log precedenti alla data indicata."""
        old_ts = datetime(2020, 1, 1, 0, 0, 0)
        recent_ts = datetime(2030, 6, 1, 12, 0, 0)
        _add_log("vecchio", ts=old_ts)
        _add_log("recente", ts=recent_ts)

        r = client.get("/api/logs/download", params={"start": "2025-01-01T00:00:00"})
        assert "recente" in r.text
        assert "vecchio" not in r.text

    def test_filter_end_excludes_future_logs(self, client):
        """Il filtro 'end' deve escludere i log successivi alla data indicata."""
        past_ts = datetime(2020, 3, 1, 10, 0, 0)
        future_ts = datetime(2035, 1, 1, 0, 0, 0)
        _add_log("passato", ts=past_ts)
        _add_log("futuro", ts=future_ts)

        r = client.get("/api/logs/download", params={"end": "2025-01-01T00:00:00"})
        assert "passato" in r.text
        assert "futuro" not in r.text

    def test_invalid_start_returns_400(self, client):
        """Un parametro 'start' non ISO deve restituire 400."""
        r = client.get("/api/logs/download", params={"start": "not-a-date"})
        assert r.status_code == 400

    def test_invalid_end_returns_400(self, client):
        """Un parametro 'end' non ISO deve restituire 400."""
        r = client.get("/api/logs/download", params={"end": "31/12/2026"})
        assert r.status_code == 400

    def test_no_filter_returns_all_logs(self, client):
        """Senza filtri devono essere restituiti tutti i log."""
        _add_log("log A")
        _add_log("log B")
        _add_log("log C")
        r = client.get("/api/logs/download")
        assert "log A" in r.text
        assert "log B" in r.text
        assert "log C" in r.text
