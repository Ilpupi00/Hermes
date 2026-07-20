"""
Test unitari per src/gui/state.py

Copre:
- WsLogHandler.emit: salva nel buffer, trimming del buffer,
  skip se no websocket/loop, invio ai websocket connessi,
  rimozione websocket disconnessi
"""
import logging
import asyncio
import pytest
from unittest.mock import MagicMock, patch

import src.gui.state as state
from src.gui.state import WsLogHandler


# ---------------------------------------------------------------------------
# Fixture: ripristina lo stato globale prima di ogni test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_state():
    """Ripristina le variabili globali di state.py prima e dopo ogni test."""
    state.log_buffer.clear()
    state.connected_websockets.clear()
    state.fastapi_loop = None
    yield
    state.log_buffer.clear()
    state.connected_websockets.clear()
    state.fastapi_loop = None


def _make_record(msg: str = "test message") -> logging.LogRecord:
    """Crea un LogRecord minimale."""
    handler = WsLogHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    record = logging.LogRecord(
        name="hermes",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None
    )
    return record, handler


# ---------------------------------------------------------------------------
# Test: WsLogHandler.emit — buffer
# ---------------------------------------------------------------------------

class TestWsLogHandlerBuffer:
    def test_emit_appends_to_buffer(self):
        """emit deve aggiungere una voce al log_buffer."""
        record, handler = _make_record("avvio worker")
        handler.emit(record)

        assert len(state.log_buffer) == 1
        assert state.log_buffer[0]["message"] == "avvio worker"

    def test_emit_entry_has_timestamp_key(self):
        """Ogni voce nel buffer deve avere la chiave 'timestamp'."""
        record, handler = _make_record("test")
        handler.emit(record)

        assert "timestamp" in state.log_buffer[0]

    def test_emit_entry_has_message_key(self):
        """Ogni voce nel buffer deve avere la chiave 'message'."""
        record, handler = _make_record("hello")
        handler.emit(record)

        assert "message" in state.log_buffer[0]

    def test_emit_multiple_records(self):
        """emit chiamato N volte deve produrre N voci nel buffer."""
        record, handler = _make_record()
        for i in range(5):
            record2, handler2 = _make_record(f"msg {i}")
            handler2.emit(record2)

        assert len(state.log_buffer) == 5

    def test_buffer_trimming_when_over_limit(self):
        """Se il buffer supera MAX_LOG_BUFFER + 100, deve essere troncato."""
        record, handler = _make_record()

        # Riempiamo il buffer oltre la soglia di trimming
        for i in range(state.MAX_LOG_BUFFER + 101):
            state.log_buffer.append({"timestamp": "T", "message": f"msg{i}"})

        # Aggiungiamo un altro record per triggerare il trimming
        record2, handler2 = _make_record("trigger trim")
        handler2.emit(record2)

        assert len(state.log_buffer) <= state.MAX_LOG_BUFFER + 1


# ---------------------------------------------------------------------------
# Test: WsLogHandler.emit — skip senza websocket/loop
# ---------------------------------------------------------------------------

class TestWsLogHandlerSkip:
    def test_emit_skips_ws_send_when_no_websockets(self):
        """Se connected_websockets è vuoto, non deve tentare invii WebSocket."""
        state.fastapi_loop = MagicMock()
        record, handler = _make_record("nessun ws")

        # Non deve sollevare eccezioni e il buffer deve essere aggiornato
        handler.emit(record)
        assert len(state.log_buffer) == 1

    def test_emit_skips_ws_send_when_no_loop(self):
        """Se fastapi_loop è None, non deve tentare invii WebSocket."""
        mock_ws = MagicMock()
        state.connected_websockets.append(mock_ws)
        state.fastapi_loop = None

        record, handler = _make_record("nessun loop")
        handler.emit(record)

        mock_ws.send_text.assert_not_called()


# ---------------------------------------------------------------------------
# Test: WsLogHandler.emit — invio ai WebSocket
# ---------------------------------------------------------------------------

class TestWsLogHandlerWebSocket:
    def test_emit_sends_to_connected_websocket(self):
        """Con un websocket connesso e un loop valido, deve inviare il messaggio."""
        mock_ws = MagicMock()
        state.connected_websockets.append(mock_ws)
        state.fastapi_loop = MagicMock()

        record, handler = _make_record("broadcast")

        with patch("src.gui.state.asyncio.run_coroutine_threadsafe") as mock_run:
            mock_run.return_value = MagicMock()
            handler.emit(record)

        mock_run.assert_called_once()

    def test_emit_removes_broken_websocket(self):
        """Se asyncio.run_coroutine_threadsafe solleva un'eccezione, il ws deve essere rimosso."""
        mock_ws = MagicMock()
        state.connected_websockets.append(mock_ws)
        state.fastapi_loop = MagicMock()

        record, handler = _make_record("crash")

        with patch("src.gui.state.asyncio.run_coroutine_threadsafe", side_effect=Exception("broken")):
            handler.emit(record)

        assert mock_ws not in state.connected_websockets

    def test_emit_sends_to_all_connected_websockets(self):
        """Se ci sono N websocket connessi, l'invio deve avvenire per ognuno."""
        mock_ws1 = MagicMock()
        mock_ws2 = MagicMock()
        state.connected_websockets.extend([mock_ws1, mock_ws2])
        state.fastapi_loop = MagicMock()

        record, handler = _make_record("multi")

        with patch("src.gui.state.asyncio.run_coroutine_threadsafe") as mock_run:
            mock_run.return_value = MagicMock()
            handler.emit(record)

        assert mock_run.call_count == 2
