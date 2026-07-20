"""
Test unitari per src/workers/dispatcher.py

Copre:
- get_worker_instance: caricamento dinamico della classe worker
- Dispatcher.__init__: pool "default" creato
- add_pool: aggiunta, duplicati, workers < 1
- remove_pool: rimozione, protezione last pool, pool not found
- update_pool: rename, resize, pool not found, workers < 1
- submit_chunk: invio al pool corretto, fallback, nessun pool disponibile
- get_pool_stats: struttura stats
- set_route / get_route / delete_route / get_routes: routing table
- shutdown: senza eccezioni
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

# Patchamo il caricamento del worker reale per non dipendere dall'AI
from src.workers.worker_base import WorkerBase, FatalWorkerError


# ---------------------------------------------------------------------------
# Fixture: Dispatcher con worker fittizio
# ---------------------------------------------------------------------------

def _make_dispatcher():
    """Crea un Dispatcher con un worker mock per evitare side-effect del costruttore."""
    with patch("src.workers.dispatcher.get_worker_instance") as mock_worker_factory:
        mock_worker = MagicMock(spec=WorkerBase)
        mock_worker_factory.return_value = mock_worker
        from src.workers.dispatcher import Dispatcher
        d = Dispatcher()
    return d


@pytest.fixture()
def dispatcher():
    d = _make_dispatcher()
    yield d
    d.shutdown()


# ---------------------------------------------------------------------------
# Test: Dispatcher.__init__
# ---------------------------------------------------------------------------

class TestDispatcherInit:
    def test_default_pool_exists(self, dispatcher):
        """Dopo l'inizializzazione deve esistere il pool 'default'."""
        assert "default" in dispatcher.pools

    def test_routing_table_is_empty(self, dispatcher):
        """La routing table iniziale deve essere vuota."""
        assert dispatcher.get_routes() == {}


# ---------------------------------------------------------------------------
# Test: add_pool
# ---------------------------------------------------------------------------

class TestAddPool:
    def test_adds_new_pool(self, dispatcher):
        result = dispatcher.add_pool("gpu", max_workers=2)
        assert result is True
        assert "gpu" in dispatcher.pools

    def test_duplicate_pool_is_rejected(self, dispatcher):
        dispatcher.add_pool("gpu", max_workers=2)
        result = dispatcher.add_pool("gpu", max_workers=4)
        assert result is False

    def test_zero_workers_is_rejected(self, dispatcher):
        result = dispatcher.add_pool("bad_pool", max_workers=0)
        assert result is False
        assert "bad_pool" not in dispatcher.pools

    def test_negative_workers_is_rejected(self, dispatcher):
        result = dispatcher.add_pool("neg_pool", max_workers=-1)
        assert result is False


# ---------------------------------------------------------------------------
# Test: remove_pool
# ---------------------------------------------------------------------------

class TestRemovePool:
    def test_removes_existing_pool(self, dispatcher):
        dispatcher.add_pool("temp", max_workers=1)
        ok, _ = dispatcher.remove_pool("temp")
        assert ok is True
        assert "temp" not in dispatcher.pools

    def test_cannot_remove_last_pool(self, dispatcher):
        # "default" è l'unico pool
        ok, msg = dispatcher.remove_pool("default")
        assert ok is False
        assert "ultimo" in msg.lower() or "pool" in msg.lower()

    def test_removes_nonexistent_pool(self, dispatcher):
        ok, _ = dispatcher.remove_pool("ghost")
        assert ok is False


# ---------------------------------------------------------------------------
# Test: update_pool
# ---------------------------------------------------------------------------

class TestUpdatePool:
    def test_rename_pool(self, dispatcher):
        dispatcher.add_pool("old", max_workers=2)
        ok, _ = dispatcher.update_pool("old", "new", new_workers=2)
        assert ok is True
        assert "new" in dispatcher.pools
        assert "old" not in dispatcher.pools

    def test_resize_pool(self, dispatcher):
        dispatcher.add_pool("resize_me", max_workers=2)
        ok, _ = dispatcher.update_pool("resize_me", "resize_me", new_workers=4)
        assert ok is True
        assert dispatcher.pools["resize_me"]._max_workers == 4

    def test_update_nonexistent_pool(self, dispatcher):
        ok, msg = dispatcher.update_pool("ghost", "ghost", new_workers=2)
        assert ok is False

    def test_update_with_zero_workers(self, dispatcher):
        ok, msg = dispatcher.update_pool("default", "default", new_workers=0)
        assert ok is False

    def test_rename_to_existing_name_is_rejected(self, dispatcher):
        dispatcher.add_pool("pool_a", max_workers=1)
        dispatcher.add_pool("pool_b", max_workers=1)
        ok, _ = dispatcher.update_pool("pool_a", "pool_b", new_workers=1)
        assert ok is False


# ---------------------------------------------------------------------------
# Test: submit_chunk
# ---------------------------------------------------------------------------

class TestSubmitChunk:
    def test_submit_to_default_pool(self, dispatcher):
        """submit_chunk deve ritornare un Future."""
        chunk = pd.DataFrame({"id_riga_input": [1], "val": ["x"]})
        metadata = {"filename": "exec_1_file_1.csv", "chunk_index": 0}

        future = dispatcher.submit_chunk(chunk, metadata, pool_name="default")

        assert future is not None

    def test_submit_fallback_to_existing_pool(self, dispatcher):
        """Se il pool richiesto non esiste, il chunk va al primo pool disponibile."""
        chunk = pd.DataFrame({"id_riga_input": [1]})
        metadata = {"filename": "exec_1_file_1.csv", "chunk_index": 0}

        # "nonexistent" non c'è → fallback su "default"
        future = dispatcher.submit_chunk(chunk, metadata, pool_name="nonexistent")
        assert future is not None

    def test_raises_when_no_pools(self, dispatcher):
        """Se tutti i pool sono stati rimossi, deve sollevare RuntimeError."""
        # Svuotiamo i pool manualmente (bypassiamo il guard remove_pool)
        with dispatcher.lock:
            dispatcher.pools.clear()

        chunk = pd.DataFrame({"a": [1]})
        with pytest.raises(RuntimeError, match="Nessun thread pool"):
            dispatcher.submit_chunk(chunk, {}, pool_name="default")


# ---------------------------------------------------------------------------
# Test: get_pool_stats
# ---------------------------------------------------------------------------

class TestGetPoolStats:
    def test_returns_dict(self, dispatcher):
        stats = dispatcher.get_pool_stats()
        assert isinstance(stats, dict)

    def test_default_pool_in_stats(self, dispatcher):
        stats = dispatcher.get_pool_stats()
        assert "default" in stats

    def test_stats_have_expected_keys(self, dispatcher):
        stats = dispatcher.get_pool_stats()
        for pool_stats in stats.values():
            assert "max_workers" in pool_stats
            assert "in_coda" in pool_stats
            assert "attivi" in pool_stats


# ---------------------------------------------------------------------------
# Test: routing table
# ---------------------------------------------------------------------------

class TestRoutingTable:
    def test_set_and_get_route(self, dispatcher):
        dispatcher.set_route("mistral-7b", "default")
        assert dispatcher.get_route("mistral-7b") == "default"

    def test_get_route_default_for_unknown_model(self, dispatcher):
        assert dispatcher.get_route("unknown-model") == "default"

    def test_delete_route(self, dispatcher):
        dispatcher.set_route("gpt-4", "default")
        result = dispatcher.delete_route("gpt-4")
        assert result is True
        assert dispatcher.get_route("gpt-4") == "default"  # fallback

    def test_delete_nonexistent_route(self, dispatcher):
        result = dispatcher.delete_route("ghost-model")
        assert result is False

    def test_get_routes_returns_copy(self, dispatcher):
        dispatcher.set_route("model-x", "default")
        routes = dispatcher.get_routes()
        routes["model-x"] = "tampered"
        # L'originale non deve essere modificato
        assert dispatcher.get_route("model-x") == "default"

    def test_set_route_falls_back_to_default_for_invalid_pool(self, dispatcher):
        """Se il pool specificato non esiste, la route deve puntare a 'default'."""
        dispatcher.set_route("llama", "nonexistent_pool")
        assert dispatcher.get_route("llama") == "default"
