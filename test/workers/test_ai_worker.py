"""
Test unitari per src/workers/ai_worker.py — LocalAIWorker

Copre:
- _is_token_valid: token valido, token vuoto, richiesta HTTP, cache
- _call_ai: chiamata al client HuggingFace e ritorno della risposta
- process: parsing del filename, FatalWorkerError su filename non valido,
           FatalWorkerError su token non valido, flusso completo OK
"""
import threading
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch, PropertyMock

from src.workers.ai_worker import LocalAIWorker
from src.workers.worker_base import FatalWorkerError


# ---------------------------------------------------------------------------
# Fixture: worker pulito prima di ogni test (svuota la cache dei token)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_token_cache():
    """Svuota la cache class-level dei token validati prima di ogni test."""
    LocalAIWorker._validated_tokens.clear()
    yield
    LocalAIWorker._validated_tokens.clear()


@pytest.fixture()
def worker():
    return LocalAIWorker()


# ---------------------------------------------------------------------------
# Test: _is_token_valid
# ---------------------------------------------------------------------------

class TestIsTokenValid:
    def test_empty_token_returns_false(self, worker):
        assert worker._is_token_valid("") is False

    def test_none_token_returns_false(self, worker):
        assert worker._is_token_valid(None) is False

    def test_valid_token_returns_true(self, worker):
        with patch("src.workers.ai_worker.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            result = worker._is_token_valid("hf_valid_token")
        assert result is True

    def test_invalid_token_returns_false(self, worker):
        with patch("src.workers.ai_worker.requests.get") as mock_get:
            mock_get.return_value.status_code = 401
            result = worker._is_token_valid("hf_bad_token")
        assert result is False

    def test_cached_result_not_re_validated(self, worker):
        """Se il token è già in cache, non deve fare ulteriori richieste HTTP."""
        LocalAIWorker._validated_tokens["hf_cached"] = True

        with patch("src.workers.ai_worker.requests.get") as mock_get:
            result = worker._is_token_valid("hf_cached")
            mock_get.assert_not_called()

        assert result is True

    def test_network_error_returns_false(self, worker):
        """Un errore di rete deve restituire False (non propagare l'eccezione)."""
        with patch("src.workers.ai_worker.requests.get", side_effect=ConnectionError("timeout")):
            result = worker._is_token_valid("hf_unreachable")
        assert result is False


# ---------------------------------------------------------------------------
# Test: _call_ai
# ---------------------------------------------------------------------------

class TestCallAi:
    def test_returns_string_response(self, worker):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="risposta generata"))]
        )

        result = worker._call_ai(mock_client, "mistral-7b", "prompt di test", 0.5, 200)

        assert result == "risposta generata"

    def test_passes_correct_parameters(self, worker):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok"))]
        )

        worker._call_ai(mock_client, "model-xyz", "my prompt", 0.3, 512)

        mock_client.chat.completions.create.assert_called_once_with(
            model="model-xyz",
            messages=[{"role": "user", "content": "my prompt"}],
            max_tokens=512,
            temperature=0.3,
        )
        mock_client.text_generation.assert_not_called()


# ---------------------------------------------------------------------------
# Test: process
# ---------------------------------------------------------------------------

class TestProcess:
    def _make_chunk(self):
        return pd.DataFrame({
            "id_riga_input": [1, 2],
            "col_a": ["x", "y"],
        })

    def test_raises_fatal_error_on_invalid_filename(self, worker):
        """Un filename che non rispetta il pattern deve sollevare FatalWorkerError."""
        metadata = {"filename": "nomefile_senza_formato.csv", "chunk_index": 0}
        chunk = self._make_chunk()

        with pytest.raises(FatalWorkerError, match="Nome file non valido"):
            worker.process(chunk, metadata)

    def test_raises_fatal_error_on_invalid_token(self, worker):
        """Se il token non è valido, deve sollevare FatalWorkerError."""
        metadata = {"filename": "job_1_file_1.csv", "chunk_index": 0}
        chunk = self._make_chunk()

        mock_context = {
            "hub_token": "bad_token",
            "nome_modello": "mistral",
            "prompt": "analizza",
            "temperatura": 0.5,
            "max_tokens": 100,
        }

        with patch("src.workers.ai_worker.SessionLocal") as mock_session_cls, \
             patch("src.workers.ai_worker.repository.get_execution_context", return_value=mock_context), \
             patch.object(worker, "_is_token_valid", return_value=False):

            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(FatalWorkerError, match="Token non valido"):
                worker.process(chunk, metadata)

    def test_process_success_returns_ok(self, worker):
        """Un flusso completo senza errori deve restituire status='ok'."""
        metadata = {"filename": "job_42_file_7.csv", "chunk_index": 0}
        chunk = self._make_chunk()

        mock_context = {
            "hub_token": "hf_ok",
            "nome_modello": "gpt-neo",
            "prompt": "processa:",
            "temperatura": 0.7,
            "max_tokens": 300,
        }

        with patch("src.workers.ai_worker.SessionLocal") as mock_session_cls, \
             patch("src.workers.ai_worker.repository.get_execution_context", return_value=mock_context), \
             patch("src.workers.ai_worker.repository.save_result"), \
             patch.object(worker, "_is_token_valid", return_value=True), \
             patch.object(worker, "_call_ai", return_value="output AI"):

            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = worker.process(chunk, metadata)

        assert result["status"] == "ok"

    def test_process_raises_fatal_on_db_error(self, worker):
        """Un errore nel recupero del contesto DB deve sollevare FatalWorkerError."""
        metadata = {"filename": "job_1_file_1.csv", "chunk_index": 0}
        chunk = self._make_chunk()

        with patch("src.workers.ai_worker.SessionLocal") as mock_session_cls, \
             patch("src.workers.ai_worker.repository.get_execution_context",
                   side_effect=ValueError("Esecuzione 1 non trovata.")):

            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(FatalWorkerError, match="Errore DB"):
                worker.process(chunk, metadata)

    def test_process_cancels_on_cancel_event(self, worker):
        """Se cancel_event è settato, deve sollevare FatalWorkerError."""
        cancel_event = threading.Event()
        cancel_event.set()

        metadata = {
            "filename": "job_5_file_3.csv",
            "chunk_index": 0,
            "cancel_event": cancel_event,
        }
        chunk = self._make_chunk()

        mock_context = {
            "hub_token": "hf_ok",
            "nome_modello": "mistral",
            "prompt": "analizza:",
            "temperatura": 0.5,
            "max_tokens": 100,
        }

        with patch("src.workers.ai_worker.SessionLocal") as mock_session_cls, \
             patch("src.workers.ai_worker.repository.get_execution_context", return_value=mock_context), \
             patch.object(worker, "_is_token_valid", return_value=True):

            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(FatalWorkerError, match="interrott"):
                worker.process(chunk, metadata)
