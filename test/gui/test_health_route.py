from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.gui.routes.health import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_health_returns_ok_when_database_is_reachable():
    connection = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = connection
    context.__exit__.return_value = False

    with patch("src.gui.routes.health.engine.connect", return_value=context):
        response = _client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    connection.execute.assert_called_once()


def test_health_returns_503_when_database_is_unreachable():
    error = OperationalError("SELECT 1", {}, Exception("connection refused"))

    with patch("src.gui.routes.health.engine.connect", side_effect=error):
        response = _client().get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "database": "unavailable",
    }
