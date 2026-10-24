"""
Test unitari per src/main.py

Copre le funzioni testabili senza avviare il processo completo:
- parse_cli_args: argomenti di default, --workers, --interval, --port
- signal_handler: setta keep_running = False
- process_inbox: inbox vuota, move error, FatalWorkerError → FAILED, flusso OK
"""
import pytest
import threading
from unittest.mock import MagicMock, patch
from pathlib import Path

import src.main as main_module
from src.workers.worker_base import FatalWorkerError


# ---------------------------------------------------------------------------
# Fixture: ripristina variabili globali
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_globals():
    original_keep_running = main_module.keep_running
    original_dispatcher = main_module.dispatcher
    yield
    main_module.keep_running = original_keep_running
    main_module.dispatcher = original_dispatcher


# ---------------------------------------------------------------------------
# Test: parse_cli_args
# ---------------------------------------------------------------------------

class TestParseCLIArgs:
    def test_default_port(self):
        """Il default di --port deve essere 8080."""
        with patch("sys.argv", ["hermes"]):
            args = main_module.parse_cli_args()
        assert args.port == 8080

    def test_custom_port(self):
        """--port deve sovrascrivere il default."""
        with patch("sys.argv", ["hermes", "--port", "9000"]):
            args = main_module.parse_cli_args()
        assert args.port == 9000

    def test_workers_is_none_by_default(self):
        """Senza --workers, args.workers deve essere None."""
        with patch("sys.argv", ["hermes"]):
            args = main_module.parse_cli_args()
        assert args.workers is None

    def test_interval_is_none_by_default(self):
        """Senza --interval, args.interval deve essere None."""
        with patch("sys.argv", ["hermes"]):
            args = main_module.parse_cli_args()
        assert args.interval is None

    def test_custom_workers(self):
        with patch("sys.argv", ["hermes", "--workers", "8"]):
            args = main_module.parse_cli_args()
        assert args.workers == 8

    def test_custom_interval(self):
        with patch("sys.argv", ["hermes", "--interval", "30"]):
            args = main_module.parse_cli_args()
        assert args.interval == 30


# ---------------------------------------------------------------------------
# Test: signal_handler
# ---------------------------------------------------------------------------

class TestSignalHandler:
    def test_signal_handler_sets_keep_running_false(self):
        """signal_handler deve impostare keep_running = False."""
        main_module.keep_running = True
        main_module.signal_handler(None, None)
        assert main_module.keep_running is False


# ---------------------------------------------------------------------------
# Test: process_inbox
# ---------------------------------------------------------------------------

class TestProcessInbox:
    def _setup_dispatcher(self):
        mock_dispatcher = MagicMock()
        main_module.dispatcher = mock_dispatcher
        return mock_dispatcher

    def test_inbox_empty_returns_immediately(self):
        """Se inbox è vuota, process_inbox deve ritornare senza fare nulla."""
        self._setup_dispatcher()
        with patch("src.main.get_next_file", return_value=None):
            main_module.process_inbox()  # Non deve sollevare eccezioni

    def test_move_file_error_returns_without_dispatch(self):
        """Se move_file fallisce, non deve avvenire alcun dispatch."""
        d = self._setup_dispatcher()
        fake_file = Path("fake_file.csv")

        with patch("src.main.get_next_file", return_value=fake_file), \
             patch("src.main.move_file", side_effect=OSError("disk full")), \
             patch(
                 "src.main.file_monitor_pool.submit",
                 side_effect=lambda fn, arg: fn(arg),
             ):
            main_module.process_inbox()

        d.submit_chunk.assert_not_called()

    def test_fatal_error_moves_file_to_failed(self):
        """Se un chunk solleva FatalWorkerError, il file deve essere spostato in FAILED."""
        self._setup_dispatcher()
        fake_file = Path("job_1_file_1.csv")
        processing = Path("processing") / fake_file.name

        mock_future = MagicMock()
        mock_future.result.side_effect = FatalWorkerError("token non valido")

        import pandas as pd
        fake_chunk = pd.DataFrame({"a": [1]})

        with patch("src.main.get_next_file", return_value=fake_file), \
             patch("src.main.move_file", return_value=processing) as mock_move, \
             patch("src.main.read_chunks", return_value=iter([fake_chunk])), \
             patch("src.main.dispatcher") as mock_disp, \
             patch("src.main.repository.get_execution_context",
                   return_value={"nome_modello": "test-model"}), \
             patch("src.main.repository.set_task_status_by_execution"), \
             patch("src.main.concurrent.futures.as_completed", return_value=iter([mock_future])), \
             patch(
                 "src.main.file_monitor_pool.submit",
                 side_effect=lambda fn, arg: fn(arg),
             ):

            mock_disp.submit_chunk.return_value = mock_future
            main_module.process_inbox()

        # Il secondo move_file deve essere verso FAILED
        assert mock_move.call_count == 2

    def test_successful_processing_logs_complete(self):
        """Un flusso completo senza errori deve completarsi senza eccezioni."""
        self._setup_dispatcher()
        fake_file = Path("job_1_file_1.csv")
        processing = Path("processing") / fake_file.name

        mock_future = MagicMock()
        mock_future.result.return_value = {"status": "ok"}

        import pandas as pd
        fake_chunk = pd.DataFrame({"a": [1]})

        with patch("src.main.get_next_file", return_value=fake_file), \
             patch("src.main.move_file", return_value=processing) as mock_move, \
             patch("src.main.read_chunks", return_value=iter([fake_chunk])), \
             patch("src.main.dispatcher") as mock_disp, \
             patch("src.main.repository.get_execution_context",
                   return_value={"nome_modello": "test-model"}), \
             patch("src.main.repository.set_task_status_by_execution"), \
             patch("src.main.concurrent.futures.as_completed", return_value=iter([mock_future])), \
             patch(
                 "src.main.file_monitor_pool.submit",
                 side_effect=lambda fn, arg: fn(arg),
             ):

            mock_disp.submit_chunk.return_value = mock_future
            main_module.process_inbox()  # Non deve sollevare eccezioni

        assert mock_move.call_count == 2
        assert mock_move.call_args_list[0].args[1] == main_module.config.PROCESSING
        assert mock_move.call_args_list[1].args[1] == main_module.config.ARCHIVE

    def test_row_errors_mark_job_failed_and_move_file(self):
        """Risultati di riga in errore non devono produrre un falso successo."""
        self._setup_dispatcher()
        fake_file = Path("job_1_file_1.csv")
        processing = Path("processing") / fake_file.name

        mock_future = MagicMock()
        mock_future.result.return_value = {
            "status": "error",
            "completed_rows": 0,
            "error_rows": 1,
        }

        import pandas as pd
        fake_chunk = pd.DataFrame({"a": [1]})

        with patch("src.main.get_next_file", return_value=fake_file), \
             patch("src.main.move_file", return_value=processing) as mock_move, \
             patch("src.main.read_chunks", return_value=iter([fake_chunk])), \
             patch("src.main.dispatcher") as mock_disp, \
             patch("src.main.repository.get_execution_context",
                   return_value={"nome_modello": "test-model"}), \
             patch("src.main.repository.set_task_status_by_execution") as mock_status, \
             patch("src.main.concurrent.futures.as_completed",
                   return_value=iter([mock_future])), \
             patch(
                 "src.main.file_monitor_pool.submit",
                 side_effect=lambda fn, arg: fn(arg),
             ):

            mock_disp.get_route.return_value = "default"
            mock_disp.submit_chunk.return_value = mock_future
            main_module.process_inbox()

        assert mock_move.call_count == 2
        assert mock_move.call_args_list[-1].args[1] == main_module.config.FAILED
        assert any(
            status_call.args[1:] == (1, "Fallito")
            for status_call in mock_status.call_args_list
        )

    def test_legacy_recovery_alias_delegates_to_reconciliation(self):
        expected = MagicMock()
        with patch("src.main.reconcile_jobs", return_value=expected) as reconcile:
            result = main_module.recover_interrupted_jobs()

        reconcile.assert_called_once_with()
        assert result is expected
