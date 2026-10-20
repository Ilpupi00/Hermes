"""
Test unitari per src/core/config.py

Copre:
- Valori di default delle variabili d'ambiente
- init_directories: creazione delle directory INBOX, ARCHIVE, FAILED
- Variabili DB di default
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch


class TestConfigDefaults:
    """Verifica i valori di default delle variabili lette da os.getenv."""

    def test_poll_interval_default(self):
        """POLL_INTERVAL deve essere un intero positivo."""
        from src.core.config import POLL_INTERVAL
        assert isinstance(POLL_INTERVAL, int)
        assert POLL_INTERVAL > 0

    def test_chunk_size_default(self):
        """CHUNK_SIZE deve essere un intero positivo."""
        from src.core.config import CHUNK_SIZE
        assert isinstance(CHUNK_SIZE, int)
        assert CHUNK_SIZE > 0

    def test_max_workers_default(self):
        """MAX_WORKERS deve essere almeno 1."""
        from src.core.config import MAX_WORKERS
        assert isinstance(MAX_WORKERS, int)
        assert MAX_WORKERS >= 1

    def test_max_retries_default(self):
        """MAX_RETRIES deve essere un intero non negativo."""
        from src.core.config import MAX_RETRIES
        assert isinstance(MAX_RETRIES, int)
        assert MAX_RETRIES >= 0

    def test_db_host_default(self):
        """DB_HOST deve avere un default non vuoto."""
        from src.core.config import DB_HOST
        assert isinstance(DB_HOST, str)
        assert len(DB_HOST) > 0

    def test_db_port_default(self):
        """DB_PORT deve essere una stringa numerica."""
        from src.core.config import DB_PORT
        assert DB_PORT.isdigit()

    def test_paths_are_path_instances(self):
        """Le directory del ciclo di vita devono essere pathlib.Path."""
        from src.core.config import (
            DATA_ROOT,
            INBOX,
            PROCESSING,
            ARCHIVE,
            FAILED,
            INTERRUPTED,
        )
        assert isinstance(DATA_ROOT, Path)
        assert isinstance(INBOX, Path)
        assert isinstance(PROCESSING, Path)
        assert isinstance(ARCHIVE, Path)
        assert isinstance(FAILED, Path)
        assert isinstance(INTERRUPTED, Path)

    def test_local_ai_base_url_default(self):
        """LOCAL_AI_BASE_URL deve iniziare con 'http'."""
        from src.core.config import LOCAL_AI_BASE_URL
        assert LOCAL_AI_BASE_URL.startswith("http")

    def test_hf_inference_provider_default(self):
        """Il routing remoto deve avere un provider esplicito e non vuoto."""
        from src.core.config import HF_INFERENCE_PROVIDER

        assert HF_INFERENCE_PROVIDER


class TestInitDirectories:
    """Verifica che init_directories crei le cartelle necessarie."""

    def test_creates_lifecycle_directories(self, tmp_path, monkeypatch):
        """Tutte le directory del ciclo di vita devono essere create."""
        inbox = tmp_path / "inbox"
        processing = tmp_path / "processing"
        archive = tmp_path / "archive"
        failed = tmp_path / "failed"
        interrupted = tmp_path / "interrupted"

        # Sostituiamo le variabili globali con i percorsi temporanei
        import src.core.config as cfg
        monkeypatch.setattr(cfg, "INBOX", inbox)
        monkeypatch.setattr(cfg, "PROCESSING", processing)
        monkeypatch.setattr(cfg, "ARCHIVE", archive)
        monkeypatch.setattr(cfg, "FAILED", failed)
        monkeypatch.setattr(cfg, "INTERRUPTED", interrupted)

        cfg.init_directories()

        assert inbox.is_dir()
        assert processing.is_dir()
        assert archive.is_dir()
        assert failed.is_dir()
        assert interrupted.is_dir()

    def test_idempotent_when_dirs_exist(self, tmp_path, monkeypatch):
        """Se le directory esistono già, init_directories non deve sollevare eccezioni."""
        inbox = tmp_path / "inbox"
        processing = tmp_path / "processing"
        archive = tmp_path / "archive"
        failed = tmp_path / "failed"
        interrupted = tmp_path / "interrupted"
        inbox.mkdir()
        processing.mkdir()
        archive.mkdir()
        failed.mkdir()
        interrupted.mkdir()

        import src.core.config as cfg
        monkeypatch.setattr(cfg, "INBOX", inbox)
        monkeypatch.setattr(cfg, "PROCESSING", processing)
        monkeypatch.setattr(cfg, "ARCHIVE", archive)
        monkeypatch.setattr(cfg, "FAILED", failed)
        monkeypatch.setattr(cfg, "INTERRUPTED", interrupted)

        # Non deve sollevare FileExistsError
        cfg.init_directories()
