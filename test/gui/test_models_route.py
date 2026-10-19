"""
Test unitari per src/gui/routes/models.py

Copre:
- GET  /api/models            : lista vuota e con modelli
- POST /api/models            : creazione OK, tipo non valido, local_url senza endpoint
- PUT  /api/models/{id}       : aggiornamento OK, 404
- DELETE /api/models/{id}     : eliminazione OK, 404
- GET  /api/models/search     : ricerca HF OK, timeout, errore HTTP
- POST /api/models/{id}/test  : hf_api OK, local_url OK, 404, tipo sconosciuto
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.gui.routes.models import router


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: client + mock repository
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _make_modello(id_modello=1, nome="mistral", tipo="hf_api", endpoint=None, desc=None):
    m = MagicMock()
    m.id_modello   = id_modello
    m.nome_modello = nome
    m.tipo         = tipo
    m.endpoint_url = endpoint
    m.descrizione  = desc
    return m


# ─────────────────────────────────────────────────────────────────────────────
# Test: GET /api/models
# ─────────────────────────────────────────────────────────────────────────────

class TestListModels:
    def test_returns_200(self, client):
        with patch("src.gui.routes.models.repository.get_all_models", return_value=[]), \
             patch("src.gui.routes.models.SessionLocal"):
            r = client.get("/api/models")
        assert r.status_code == 200

    def test_empty_returns_empty_list(self, client):
        with patch("src.gui.routes.models.repository.get_all_models", return_value=[]), \
             patch("src.gui.routes.models.SessionLocal"):
            r = client.get("/api/models")
        assert r.json()["models"] == []

    def test_returns_model_fields(self, client):
        m = _make_modello(1, "mistral", "hf_api", None, "Modello veloce")
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.get_all_models", return_value=[m]), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.get("/api/models")
        models = r.json()["models"]
        assert len(models) == 1
        assert models[0]["nome_modello"] == "mistral"
        assert models[0]["tipo"] == "hf_api"


# ─────────────────────────────────────────────────────────────────────────────
# Test: POST /api/models
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateModel:
    def test_create_hf_api_success(self, client):
        m = _make_modello(1, "mistral", "hf_api")
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.create_model", return_value=m), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.post("/api/models", json={"nome_modello": "mistral", "tipo": "hf_api"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_create_local_url_without_endpoint_returns_400(self, client):
        r = client.post("/api/models", json={"nome_modello": "llama", "tipo": "local_url"})
        assert r.status_code == 400

    def test_invalid_tipo_returns_400(self, client):
        r = client.post("/api/models", json={"nome_modello": "x", "tipo": "unknown_tipo"})
        assert r.status_code == 400

    def test_create_local_url_with_endpoint_success(self, client):
        m = _make_modello(2, "llama3", "local_url", "http://localhost:11434/v1")
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.create_model", return_value=m), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.post("/api/models", json={
                "nome_modello": "llama3", "tipo": "local_url",
                "endpoint_url": "http://localhost:11434/v1"
            })
        assert r.status_code == 200
        assert r.json()["success"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Test: PUT /api/models/{id}
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateModel:
    def test_update_success(self, client):
        m = _make_modello(1, "mistral-updated", "hf_api")
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.update_model", return_value=m), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.put("/api/models/1", json={"nome_modello": "mistral-updated"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_update_not_found_returns_404(self, client):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.update_model", return_value=None), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.put("/api/models/99", json={"nome_modello": "x"})
        assert r.status_code == 404

    def test_invalid_tipo_returns_400(self, client):
        r = client.put("/api/models/1", json={"tipo": "bad_tipo"})
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Test: DELETE /api/models/{id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteModel:
    def test_delete_success(self, client):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.delete_model", return_value=True), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.delete("/api/models/1")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_delete_not_found_returns_404(self, client):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.delete_model", return_value=False), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.delete("/api/models/99")
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Test: GET /api/models/search
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchHuggingFace:
    def _mock_hf_response(self, models_data):
        import requests as req
        mock_resp = MagicMock()
        mock_resp.json.return_value = models_data
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_search_returns_results(self, client):
        fake_models = [
            {"id": "mistralai/Mistral-7B", "pipeline_tag": "text-generation",
             "likes": 1000, "downloads": 50000, "tags": ["pytorch"], "private": False}
        ]
        with patch("src.gui.routes.models.http_requests.get",
                   return_value=self._mock_hf_response(fake_models)):
            r = client.get("/api/models/search", params={"q": "mistral"})
        assert r.status_code == 200
        assert len(r.json()["results"]) == 1
        assert r.json()["results"][0]["id"] == "mistralai/Mistral-7B"

    def test_empty_query_returns_results(self, client):
        with patch("src.gui.routes.models.http_requests.get",
                   return_value=self._mock_hf_response([])):
            r = client.get("/api/models/search")
        assert r.status_code == 200
        assert r.json()["results"] == []

    def test_timeout_returns_504(self, client):
        import requests as req
        with patch("src.gui.routes.models.http_requests.get",
                   side_effect=req.Timeout("timeout")):
            r = client.get("/api/models/search", params={"q": "test"})
        assert r.status_code == 504

    def test_http_error_returns_502(self, client):
        import requests as req
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError("502")
        with patch("src.gui.routes.models.http_requests.get", return_value=mock_resp):
            r = client.get("/api/models/search", params={"q": "test"})
        assert r.status_code == 502


# ─────────────────────────────────────────────────────────────────────────────
# Test: POST /api/models/{id}/test
# ─────────────────────────────────────────────────────────────────────────────

class TestTestModel:
    def _mock_session(self, modello):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        return mock_ctx

    def test_model_not_found_returns_404(self, client):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.get_model_by_id", return_value=None), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.post("/api/models/99/test", json={"prompt": "test"})
        assert r.status_code == 404

    def test_hf_api_without_token_returns_error(self, client):
        m = _make_modello(1, "mistral", "hf_api")
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.get_model_by_id", return_value=m), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.post("/api/models/1/test", json={"prompt": "test"})
        assert r.json()["status"] == "error"

    def test_local_url_without_endpoint_returns_error(self, client):
        m = _make_modello(2, "llama3", "local_url", None)
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.get_model_by_id", return_value=m), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.post("/api/models/2/test", json={"prompt": "test"})
        assert r.json()["status"] == "error"

    def test_unknown_tipo_returns_error(self, client):
        m = _make_modello(3, "unknown", "bad_tipo")
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        with patch("src.gui.routes.models.repository.get_model_by_id", return_value=m), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx):
            r = client.post("/api/models/3/test", json={"prompt": "test"})
        assert r.json()["status"] == "error"

    def test_hf_api_success(self, client):
        m = _make_modello(1, "mistral", "hf_api")
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Ciao!"))]
        )

        with patch("src.gui.routes.models.repository.get_model_by_id", return_value=m), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx), \
             patch("src.gui.routes.models.InferenceClient", return_value=mock_client):
            r = client.post("/api/models/1/test", json={"hub_token": "hf_abc", "prompt": "test"})
        assert r.json()["status"] == "ok"
        assert "Ciao!" in r.json()["risposta"]
        mock_client.chat.completions.create.assert_called_once_with(
            model="mistral",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=50,
            temperature=0.1,
        )
        mock_client.text_generation.assert_not_called()

    def test_local_url_success(self, client):
        m = _make_modello(2, "llama3", "local_url", "http://localhost:11434/v1")
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__  = MagicMock(return_value=False)
        mock_oa = MagicMock()
        mock_oa.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Risposta locale"))]
        )
        with patch("src.gui.routes.models.repository.get_model_by_id", return_value=m), \
             patch("src.gui.routes.models.SessionLocal", return_value=mock_ctx), \
             patch("src.gui.routes.models.openai.OpenAI", return_value=mock_oa):
            r = client.post("/api/models/2/test", json={"prompt": "test"})
        assert r.json()["status"] == "ok"
        assert r.json()["risposta"] == "Risposta locale"
