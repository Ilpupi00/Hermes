"""
Test unitari per src/workers/hybrid_worker.py

Copre:
- _is_token_valid: token valido, non valido, cache
- _call_hf_api: chiamata a InferenceClient.chat.completions.create
- _call_local_api: chiamata a openai.OpenAI.chat.completions.create
- process:
    - flusso completo hf_api (mock)
    - flusso completo local_url (mock)
    - nome file non valido → FatalWorkerError
    - DB error → FatalWorkerError
    - token non valido → FatalWorkerError
    - endpoint_url mancante per local_url → FatalWorkerError
    - tipo sconosciuto → FatalWorkerError
"""
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from src.workers.hybrid_worker import HybridWorker
from src.workers.worker_base import FatalWorkerError


@pytest.fixture(autouse=True)
def clear_token_cache():
    """Svuota la cache dei token tra un test e l'altro."""
    HybridWorker._validated_tokens.clear()
    yield
    HybridWorker._validated_tokens.clear()


@pytest.fixture
def worker():
    return HybridWorker()


@pytest.fixture
def fake_chunk():
    return pd.DataFrame({"id_riga_input": [1, 2], "testo": ["ciao", "mondo"]})


@pytest.fixture
def good_context_hf():
    return {
        "hub_token":    "hf_abc123",
        "prompt":       "Analizza: {testo}",
        "prompt_mapping": {"testo": "testo"},
        "nome_modello": "mistralai/Mistral-7B-Instruct-v0.3",
        "tipo":         "hf_api",
        "endpoint_url": None,
        "temperatura":  0.1,
        "max_tokens":   100,
        "id_file":      2,
    }


@pytest.fixture
def good_context_local():
    return {
        "hub_token":    None,
        "prompt":       "Analizza: {testo}",
        "prompt_mapping": {"testo": "testo"},
        "nome_modello": "llama3",
        "tipo":         "local_url",
        "endpoint_url": "http://localhost:11434/v1",
        "temperatura":  0.1,
        "max_tokens":   100,
        "id_file":      2,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test: _is_token_valid
# ─────────────────────────────────────────────────────────────────────────────

class TestIsTokenValid:
    def test_empty_token_returns_false(self, worker):
        assert worker._is_token_valid("") is False

    def test_none_token_returns_false(self, worker):
        assert worker._is_token_valid(None) is False

    def test_valid_token_returns_true(self, worker):
        with patch("src.workers.hybrid_worker.requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            result = worker._is_token_valid("hf_valid")
        assert result is True

    def test_invalid_token_returns_false(self, worker):
        with patch("src.workers.hybrid_worker.requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=401)
            result = worker._is_token_valid("hf_bad")
        assert result is False

    def test_cache_avoids_double_request(self, worker):
        with patch("src.workers.hybrid_worker.requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            worker._is_token_valid("hf_cached")
            worker._is_token_valid("hf_cached")
        assert mock_get.call_count == 1

    def test_network_error_returns_false(self, worker):
        with patch("src.workers.hybrid_worker.requests.get", side_effect=Exception("timeout")):
            result = worker._is_token_valid("hf_error")
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# Test: _call_hf_api
# ─────────────────────────────────────────────────────────────────────────────

class TestCallHfApi:
    def test_returns_chat_completion_content(self, worker):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Risposta AI"))]
        )
        result = worker._call_hf_api(
            client=mock_client,
            model="mistralai/Mistral-7B",
            prompt="Ciao",
            temperature=0.1,
            max_tokens=50,
        )
        assert result == "Risposta AI"

    def test_passes_correct_parameters(self, worker):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok"))]
        )
        worker._call_hf_api(
            client=mock_client,
            model="mistral",
            prompt="test",
            temperature=0.7,
            max_tokens=200,
        )
        mock_client.chat.completions.create.assert_called_once_with(
            model="mistral",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=200,
            temperature=0.7,
        )
        mock_client.text_generation.assert_not_called()

    def test_unsupported_model_is_fatal_without_retry(self, worker):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "model_not_supported: not supported by any provider you have enabled"
        )

        with pytest.raises(FatalWorkerError, match="Inference Providers"):
            worker._call_hf_api(
                client=mock_client,
                model="Qwen/Qwen2.5-0.5B-Instruct",
                prompt="Ciao",
                temperature=0.1,
                max_tokens=50,
            )

        mock_client.chat.completions.create.assert_called_once()

    def test_exhausted_credits_are_fatal_without_retry(self, worker):
        mock_client = MagicMock()
        billing_error = Exception(
            "402 Payment Required: You have no remaining credits."
        )
        billing_error.response = MagicMock(status_code=402)
        mock_client.chat.completions.create.side_effect = billing_error

        with pytest.raises(FatalWorkerError, match="Credito Hugging Face"):
            worker._call_hf_api(
                client=mock_client,
                model="Qwen/Qwen2.5-0.5B-Instruct",
                prompt="Ciao",
                temperature=0.1,
                max_tokens=50,
            )

        mock_client.chat.completions.create.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Test: _call_local_api
# ─────────────────────────────────────────────────────────────────────────────

class TestCallLocalApi:
    def test_returns_chat_completion_content(self, worker):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Risposta locale"))]
        )
        result = worker._call_local_api(
            client=mock_client,
            model="llama3",
            prompt="Ciao",
            temperature=0.1,
            max_tokens=50,
        )
        assert result == "Risposta locale"

    def test_passes_correct_parameters(self, worker):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok"))]
        )
        worker._call_local_api(
            client=mock_client,
            model="phi3",
            prompt="test prompt",
            temperature=0.5,
            max_tokens=100,
        )
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "phi3"
        assert call_args.kwargs["temperature"] == 0.5
        assert call_args.kwargs["max_tokens"] == 100
        assert call_args.kwargs["messages"][0]["content"] == "test prompt"


# ─────────────────────────────────────────────────────────────────────────────
# Test: process — errori di input e configurazione
# ─────────────────────────────────────────────────────────────────────────────

class TestProcessErrors:
    def test_invalid_filename_raises_fatal_error(self, worker, fake_chunk):
        with pytest.raises(FatalWorkerError, match="non valido"):
            worker.process(fake_chunk, {"filename": "wrong_name.csv"})

    def test_db_error_raises_fatal_error(self, worker, fake_chunk):
        with patch("src.workers.hybrid_worker.repository.get_execution_context",
                   side_effect=ValueError("DB error")):
            with patch("src.workers.hybrid_worker.SessionLocal") as mock_session:
                mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
                mock_session.return_value.__exit__  = MagicMock(return_value=False)
                with pytest.raises(FatalWorkerError, match="Errore DB"):
                    worker.process(fake_chunk, {"filename": "exec_1_file_2.csv"})

    def test_invalid_token_hf_api_raises_fatal_error(self, worker, fake_chunk, good_context_hf):
        with patch("src.workers.hybrid_worker.repository.get_execution_context",
                   return_value=good_context_hf), \
             patch("src.workers.hybrid_worker.SessionLocal") as mock_session, \
             patch.object(worker, "_is_token_valid", return_value=False):
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__  = MagicMock(return_value=False)
            with pytest.raises(FatalWorkerError, match="Token HuggingFace"):
                worker.process(fake_chunk, {"filename": "exec_1_file_2.csv"})

    def test_missing_endpoint_url_raises_fatal_error(self, worker, fake_chunk, good_context_local):
        ctx = {**good_context_local, "endpoint_url": None}
        with patch("src.workers.hybrid_worker.repository.get_execution_context", return_value=ctx), \
             patch("src.workers.hybrid_worker.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__  = MagicMock(return_value=False)
            with pytest.raises(FatalWorkerError, match="endpoint_url"):
                worker.process(fake_chunk, {"filename": "exec_1_file_2.csv"})

    def test_unknown_tipo_raises_fatal_error(self, worker, fake_chunk):
        ctx = {
            "hub_token": None, "prompt": "x", "nome_modello": "x",
            "tipo": "unknown_mode", "endpoint_url": None,
            "temperatura": 0.1, "max_tokens": 50,
            "id_file": 2,
        }
        with patch("src.workers.hybrid_worker.repository.get_execution_context", return_value=ctx), \
             patch("src.workers.hybrid_worker.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__  = MagicMock(return_value=False)
            with pytest.raises(FatalWorkerError, match="sconosciuto"):
                worker.process(fake_chunk, {"filename": "exec_1_file_2.csv"})


# ─────────────────────────────────────────────────────────────────────────────
# Test: process — flusso completo
# ─────────────────────────────────────────────────────────────────────────────

class TestProcessSuccess:
    def _mock_session(self):
        mock_db = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.__exit__  = MagicMock(return_value=False)
        return mock_ctx, mock_db

    def test_hf_api_full_flow(self, worker, fake_chunk, good_context_hf):
        mock_ctx, mock_db = self._mock_session()
        with patch("src.workers.hybrid_worker.repository.get_execution_context",
                   return_value=good_context_hf), \
             patch("src.workers.hybrid_worker.SessionLocal", return_value=mock_ctx), \
             patch.object(worker, "_is_token_valid", return_value=True), \
             patch(
                 "src.workers.hybrid_worker.repository.get_input_row_ids",
                 return_value={0: 1, 1: 2},
             ), \
             patch.object(worker, "_call_hf_api", return_value="Risposta OK") as mock_call, \
             patch("src.workers.hybrid_worker.repository.save_result"):

            result = worker.process(fake_chunk, {"filename": "exec_1_file_2.csv"})

        assert result["status"] == "ok"
        assert result["completed_rows"] == 2
        assert result["error_rows"] == 0
        assert mock_call.call_count == len(fake_chunk)
        assert mock_call.call_args_list[0].args[2] == "Analizza: ciao"
        assert mock_call.call_args_list[1].args[2] == "Analizza: mondo"

    def test_local_url_full_flow(self, worker, fake_chunk, good_context_local):
        mock_ctx, mock_db = self._mock_session()
        with patch("src.workers.hybrid_worker.repository.get_execution_context",
                   return_value=good_context_local), \
             patch("src.workers.hybrid_worker.SessionLocal", return_value=mock_ctx), \
             patch(
                 "src.workers.hybrid_worker.repository.get_input_row_ids",
                 return_value={0: 1, 1: 2},
             ), \
             patch.object(worker, "_call_local_api", return_value="Risposta locale") as mock_call, \
             patch("src.workers.hybrid_worker.openai.OpenAI"), \
             patch("src.workers.hybrid_worker.repository.save_result"):

            result = worker.process(fake_chunk, {"filename": "exec_1_file_2.csv"})

        assert result["status"] == "ok"
        assert result["completed_rows"] == 2
        assert result["error_rows"] == 0
        assert mock_call.call_count == len(fake_chunk)
        assert mock_call.call_args_list[0].args[2] == "Analizza: ciao"

    def test_plain_prompt_preserves_legacy_row_context(
        self, worker, fake_chunk, good_context_local
    ):
        context = {
            **good_context_local,
            "prompt": "Analizza i dati.",
            "prompt_mapping": {},
        }
        mock_ctx, mock_db = self._mock_session()
        with patch(
            "src.workers.hybrid_worker.repository.get_execution_context",
            return_value=context,
        ), patch(
            "src.workers.hybrid_worker.SessionLocal", return_value=mock_ctx
        ), patch(
            "src.workers.hybrid_worker.repository.get_input_row_ids",
            return_value={0: 1, 1: 2},
        ), patch.object(
            worker, "_call_local_api", return_value="Risposta locale"
        ) as mock_call, patch(
            "src.workers.hybrid_worker.openai.OpenAI"
        ), patch(
            "src.workers.hybrid_worker.repository.save_result"
        ):
            worker.process(fake_chunk, {"filename": "exec_1_file_2.csv"})

        first_prompt = mock_call.call_args_list[0].args[2]
        assert first_prompt.startswith("Analizza i dati.\n\nDati:\n")
        assert "'testo': 'ciao'" in first_prompt

    def test_row_error_saves_errore_stato(self, worker, fake_chunk, good_context_hf):
        """Se una riga fallisce, deve salvare stato='Errore' senza interrompere il processo."""
        mock_ctx, mock_db = self._mock_session()
        with patch("src.workers.hybrid_worker.repository.get_execution_context",
                   return_value=good_context_hf), \
             patch("src.workers.hybrid_worker.SessionLocal", return_value=mock_ctx), \
             patch.object(worker, "_is_token_valid", return_value=True), \
             patch(
                 "src.workers.hybrid_worker.repository.get_input_row_ids",
                 return_value={0: 1, 1: 2},
             ), \
             patch.object(worker, "_call_hf_api", side_effect=Exception("API down")), \
             patch("src.workers.hybrid_worker.repository.save_result") as mock_save:

            result = worker.process(
                fake_chunk, {"filename": "exec_1_file_2.csv"}
            )

        # Tutte le righe devono essere salvate con stato='Errore'
        for call in mock_save.call_args_list:
            assert call.kwargs.get("stato") == "Errore" or call.args[-1] == "Errore"
        assert result["status"] == "error"
        assert result["completed_rows"] == 0
        assert result["error_rows"] == 2

    def test_fatal_row_error_is_propagated(
        self, worker, fake_chunk, good_context_hf
    ):
        mock_ctx, mock_db = self._mock_session()
        with patch(
            "src.workers.hybrid_worker.repository.get_execution_context",
            return_value=good_context_hf,
        ), patch(
            "src.workers.hybrid_worker.SessionLocal", return_value=mock_ctx
        ), patch.object(
            worker, "_is_token_valid", return_value=True
        ), patch(
            "src.workers.hybrid_worker.repository.get_input_row_ids",
            return_value={0: 1, 1: 2},
        ), patch.object(
            worker,
            "_call_hf_api",
            side_effect=FatalWorkerError("provider non abilitato"),
        ) as mock_call, patch(
            "src.workers.hybrid_worker.repository.save_result"
        ) as mock_save:
            with pytest.raises(FatalWorkerError, match="provider non abilitato"):
                worker.process(
                    fake_chunk, {"filename": "exec_1_file_2.csv"}
                )

        mock_call.assert_called_once()
        mock_save.assert_not_called()
