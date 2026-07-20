"""
Test unitari per src/gui/routes/dashboard.py

Copre:
- GET /: risponde 200 con contenuto HTML
"""
import pytest
import os
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, mock_open

from src.gui.routes.dashboard import router


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestDashboardRoute:
    def test_get_root_returns_200(self, client):
        """GET / deve restituire 200 con contenuto HTML."""
        html_content = "<html><body><h1>Hermes</h1></body></html>"
        with patch("builtins.open", mock_open(read_data=html_content)):
            r = client.get("/")
        assert r.status_code == 200

    def test_get_root_returns_html_content_type(self, client):
        """La risposta deve avere Content-Type text/html."""
        html_content = "<html></html>"
        with patch("builtins.open", mock_open(read_data=html_content)):
            r = client.get("/")
        assert "text/html" in r.headers.get("content-type", "")

    def test_get_root_body_matches_html_file(self, client):
        """Il corpo della risposta deve coincidere con il file HTML."""
        html_content = "<html><body>Test Dashboard</body></html>"
        with patch("builtins.open", mock_open(read_data=html_content)):
            r = client.get("/")
        assert "Test Dashboard" in r.text
