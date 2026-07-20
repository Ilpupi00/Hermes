"""
Test unitari per src/gui/routes/control.py

Usa FastAPI TestClient con mock del dispatcher e dello stato.
Copre:
- GET  /api/status       : online/offline, pool stats
- POST /api/pools        : crea pool, hermes offline
- DELETE /api/pools/{n}  : elimina pool, hermes offline
- PUT  /api/pools/{n}    : aggiorna pool, hermes offline
- POST /api/routes       : set route, hermes offline
- GET  /api/routes       : get routes, hermes offline
- DELETE /api/routes/{m} : delete route, hermes offline
- POST /api/start        : avvio quando già running, avvio a freddo
- POST /api/stop         : stop
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.gui.routes.control import router
import src.gui.state as state
import src.main as hermes_main


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_globals():
    """Ripristina lo stato globale prima di ogni test."""
    original_dispatcher = hermes_main.dispatcher
    original_keep_running = hermes_main.keep_running
    original_thread = state.SCHEDULER_THREAD
    yield
    hermes_main.dispatcher = original_dispatcher
    hermes_main.keep_running = original_keep_running
    state.SCHEDULER_THREAD = original_thread


def _mock_dispatcher():
    """Crea un mock del Dispatcher e lo assegna a hermes_main."""
    d = MagicMock()
    d.get_pool_stats.return_value = {"default": {"max_workers": 4, "in_coda": 0, "attivi": "In attesa"}}
    d.add_pool.return_value = True
    d.remove_pool.return_value = (True, "Pool eliminato.")
    d.update_pool.return_value = (True, "Pool aggiornato.")
    d.set_route.return_value = True
    d.get_routes.return_value = {"model-x": "default"}
    d.delete_route.return_value = True
    hermes_main.dispatcher = d
    return d


# ---------------------------------------------------------------------------
# Test: GET /api/status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_returns_200(self, client):
        hermes_main.dispatcher = None
        state.SCHEDULER_THREAD = None
        r = client.get("/api/status")
        assert r.status_code == 200

    def test_is_running_false_when_no_thread(self, client):
        hermes_main.dispatcher = None
        state.SCHEDULER_THREAD = None
        r = client.get("/api/status")
        assert r.json()["is_running"] is False

    def test_is_running_true_when_thread_alive(self, client):
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        state.SCHEDULER_THREAD = mock_thread
        hermes_main.dispatcher = None
        r = client.get("/api/status")
        assert r.json()["is_running"] is True

    def test_includes_pool_stats_when_dispatcher_present(self, client):
        d = _mock_dispatcher()
        state.SCHEDULER_THREAD = None
        r = client.get("/api/status")
        data = r.json()
        assert "pools" in data
        d.get_pool_stats.assert_called_once()


# ---------------------------------------------------------------------------
# Test: POST /api/pools
# ---------------------------------------------------------------------------

class TestCreatePool:
    def test_create_pool_success(self, client):
        d = _mock_dispatcher()
        r = client.post("/api/pools", json={"name": "gpu", "workers": 2})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_create_pool_offline(self, client):
        hermes_main.dispatcher = None
        r = client.post("/api/pools", json={"name": "gpu", "workers": 2})
        assert r.json()["success"] is False

    def test_create_pool_validation_error_zero_workers(self, client):
        r = client.post("/api/pools", json={"name": "bad", "workers": 0})
        assert r.status_code == 422  # FastAPI validation


# ---------------------------------------------------------------------------
# Test: DELETE /api/pools/{pool_name}
# ---------------------------------------------------------------------------

class TestDeletePool:
    def test_delete_pool_success(self, client):
        _mock_dispatcher()
        r = client.delete("/api/pools/gpu")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_delete_pool_offline(self, client):
        hermes_main.dispatcher = None
        r = client.delete("/api/pools/gpu")
        assert r.json()["success"] is False


# ---------------------------------------------------------------------------
# Test: PUT /api/pools/{pool_name}
# ---------------------------------------------------------------------------

class TestUpdatePool:
    def test_update_pool_success(self, client):
        _mock_dispatcher()
        r = client.put("/api/pools/default", json={"new_name": "default", "workers": 8})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_update_pool_offline(self, client):
        hermes_main.dispatcher = None
        r = client.put("/api/pools/default", json={"new_name": "default", "workers": 2})
        assert r.json()["success"] is False


# ---------------------------------------------------------------------------
# Test: POST /api/routes
# ---------------------------------------------------------------------------

class TestSetRoute:
    def test_set_route_success(self, client):
        _mock_dispatcher()
        r = client.post("/api/routes", json={"model_name": "llama", "pool_name": "default"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_set_route_offline(self, client):
        hermes_main.dispatcher = None
        r = client.post("/api/routes", json={"model_name": "llama", "pool_name": "default"})
        assert r.json()["success"] is False


# ---------------------------------------------------------------------------
# Test: GET /api/routes
# ---------------------------------------------------------------------------

class TestGetRoutes:
    def test_get_routes_returns_dict(self, client):
        _mock_dispatcher()
        r = client.get("/api/routes")
        assert "routes" in r.json()

    def test_get_routes_offline_returns_empty(self, client):
        hermes_main.dispatcher = None
        r = client.get("/api/routes")
        assert r.json()["routes"] == {}


# ---------------------------------------------------------------------------
# Test: DELETE /api/routes/{model_name}
# ---------------------------------------------------------------------------

class TestDeleteRoute:
    def test_delete_route_success(self, client):
        _mock_dispatcher()
        r = client.delete("/api/routes/llama")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_delete_route_offline(self, client):
        hermes_main.dispatcher = None
        r = client.delete("/api/routes/llama")
        assert r.json()["success"] is False


# ---------------------------------------------------------------------------
# Test: POST /api/start
# ---------------------------------------------------------------------------

class TestStartHermes:
    def test_start_returns_already_running(self, client):
        """Se il thread è già vivo, deve rispondere 'already_running'."""
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        state.SCHEDULER_THREAD = mock_thread

        r = client.post("/api/start", json={"workers": 2, "interval": 30})
        assert r.json()["status"] == "already_running"

    def test_start_launches_thread(self, client):
        """Se Hermes non è in running, deve avviare un thread e rispondere 'started'."""
        state.SCHEDULER_THREAD = None
        hermes_main.dispatcher = None

        with patch("src.gui.routes.control.threading.Thread") as mock_thread_cls, \
             patch("src.gui.routes.control.hermes_main.Dispatcher") as mock_disp_cls, \
             patch("src.gui.routes.control.config.init_directories"):

            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread
            mock_disp_cls.return_value = MagicMock()

            r = client.post("/api/start", json={"workers": 4, "interval": 60})

        assert r.json()["status"] == "started"
        mock_thread.start.assert_called_once()


# ---------------------------------------------------------------------------
# Test: POST /api/stop
# ---------------------------------------------------------------------------

class TestStopHermes:
    def test_stop_returns_stopped(self, client):
        hermes_main.dispatcher = None
        r = client.post("/api/stop")
        assert r.json()["status"] == "stopped"

    def test_stop_calls_dispatcher_shutdown(self, client):
        d = _mock_dispatcher()
        r = client.post("/api/stop")
        d.shutdown.assert_called_once()
        assert r.json()["status"] == "stopped"

    def test_stop_sets_keep_running_false(self, client):
        hermes_main.keep_running = True
        hermes_main.dispatcher = None
        client.post("/api/stop")
        assert hermes_main.keep_running is False
