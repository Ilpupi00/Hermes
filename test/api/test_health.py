"""
Test unitari per src/api/health.py

Copre:
- HealthCheckHandler.do_GET /health → 200 + JSON corretto
- HealthCheckHandler.do_GET altra rotta → 404
- start_health_server: avvio del server su un thread daemon
"""
import json
import pytest
from io import BytesIO
from unittest.mock import MagicMock, patch
from http.server import BaseHTTPRequestHandler

from src.api.health import HealthCheckHandler, start_health_server


# ---------------------------------------------------------------------------
# Helper per simulare una richiesta HTTP al handler
# ---------------------------------------------------------------------------

class _FakeSocket:
    """Socket minimale che permette a wfile di accumulare la risposta."""

    def __init__(self):
        self._buffer = BytesIO()
        self.makefile_buffer = BytesIO()

    def makefile(self, mode, bufsize=None):
        return self.makefile_buffer

    def sendall(self, data):
        self._buffer.write(data)

    @property
    def response_bytes(self):
        return self._buffer.getvalue()


def _make_handler(path: str) -> HealthCheckHandler:
    """
    Instanzia il handler senza avviare un vero server HTTP.
    Bypassa __init__ di BaseHTTPRequestHandler e imposta manualmente
    i campi necessari.
    """
    handler = HealthCheckHandler.__new__(HealthCheckHandler)
    handler.path = path

    # Simula wfile come buffer scrivibile
    handler.wfile = BytesIO()

    # Accumuliamo gli header in un buffer separato per semplicità
    handler._headers_buffer = BytesIO()

    # Patch dei metodi di risposta HTTP
    responses_sent = []

    def fake_send_response(code):
        responses_sent.append(code)

    def fake_send_header(key, value):
        pass

    def fake_end_headers():
        pass

    handler.send_response = fake_send_response
    handler.send_header = fake_send_header
    handler.end_headers = fake_end_headers
    handler._responses_sent = responses_sent

    return handler


# ---------------------------------------------------------------------------
# Test: /health route
# ---------------------------------------------------------------------------

class TestHealthCheckHandlerHealth:
    def test_responds_200_on_health_route(self):
        handler = _make_handler("/health")
        handler.do_GET()
        assert 200 in handler._responses_sent

    def test_response_body_is_valid_json(self):
        handler = _make_handler("/health")
        handler.do_GET()
        body = handler.wfile.getvalue()
        payload = json.loads(body.decode("utf-8"))
        assert isinstance(payload, dict)

    def test_response_status_is_ok(self):
        handler = _make_handler("/health")
        handler.do_GET()
        body = handler.wfile.getvalue()
        payload = json.loads(body.decode("utf-8"))
        assert payload["status"] == "ok"

    def test_response_includes_service_name(self):
        handler = _make_handler("/health")
        handler.do_GET()
        body = handler.wfile.getvalue()
        payload = json.loads(body.decode("utf-8"))
        assert payload["service"] == "hermes_scheduler"

    def test_response_includes_active_workers(self):
        handler = _make_handler("/health")
        handler.do_GET()
        body = handler.wfile.getvalue()
        payload = json.loads(body.decode("utf-8"))
        assert "active_workers" in payload
        assert isinstance(payload["active_workers"], int)

    def test_response_includes_poll_interval(self):
        handler = _make_handler("/health")
        handler.do_GET()
        body = handler.wfile.getvalue()
        payload = json.loads(body.decode("utf-8"))
        assert "poll_interval_sec" in payload


# ---------------------------------------------------------------------------
# Test: rotta non trovata
# ---------------------------------------------------------------------------

class TestHealthCheckHandlerNotFound:
    def test_responds_404_on_unknown_route(self):
        handler = _make_handler("/unknown")
        handler.do_GET()
        assert 404 in handler._responses_sent

    def test_responds_404_on_root_route(self):
        handler = _make_handler("/")
        handler.do_GET()
        assert 404 in handler._responses_sent

    def test_404_has_empty_body(self):
        handler = _make_handler("/metrics")
        handler.do_GET()
        # La rotta non-health non deve scrivere body
        assert handler.wfile.getvalue() == b""


# ---------------------------------------------------------------------------
# Test: start_health_server
# ---------------------------------------------------------------------------

class TestStartHealthServer:
    def test_returns_server_object(self):
        """start_health_server deve restituire un oggetto HTTPServer."""
        with patch("src.api.health.HTTPServer") as mock_server_cls, \
             patch("src.api.health.threading.Thread") as mock_thread_cls:

            mock_server = MagicMock()
            mock_server_cls.return_value = mock_server
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            result = start_health_server(port=19999)

        assert result == mock_server

    def test_thread_is_started(self):
        """Il thread del server deve essere avviato."""
        with patch("src.api.health.HTTPServer") as mock_server_cls, \
             patch("src.api.health.threading.Thread") as mock_thread_cls:

            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            start_health_server(port=19999)

        mock_thread.start.assert_called_once()

    def test_thread_is_daemon(self):
        """Il thread deve essere configurato come daemon."""
        with patch("src.api.health.HTTPServer"), \
             patch("src.api.health.threading.Thread") as mock_thread_cls:

            start_health_server(port=19999)

            _, kwargs = mock_thread_cls.call_args
            assert kwargs.get("daemon") is True