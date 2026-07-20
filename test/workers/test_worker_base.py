"""
Test unitari per src/workers/worker_base.py

Copre:
- FatalWorkerError: è una sottoclasse di Exception, messaggio corretto
- WorkerBase: è una ABC, non istanziabile direttamente,
  richiede l'implementazione di process()
"""
import pytest
from src.workers.worker_base import FatalWorkerError, WorkerBase
import pandas as pd


class TestFatalWorkerError:
    def test_is_exception_subclass(self):
        """FatalWorkerError deve essere una sottoclasse di Exception."""
        assert issubclass(FatalWorkerError, Exception)

    def test_can_be_raised_and_caught(self):
        """Deve poter essere sollevata e catturata come Exception."""
        with pytest.raises(FatalWorkerError):
            raise FatalWorkerError("errore fatale")

    def test_message_is_preserved(self):
        """Il messaggio passato deve essere accessibile dall'eccezione."""
        msg = "Token non valido"
        exc = FatalWorkerError(msg)
        assert str(exc) == msg

    def test_caught_as_generic_exception(self):
        """FatalWorkerError deve poter essere catturata come Exception generica."""
        caught = False
        try:
            raise FatalWorkerError("test")
        except Exception:
            caught = True
        assert caught


class TestWorkerBase:
    def test_cannot_be_instantiated_directly(self):
        """WorkerBase è una ABC: non deve poter essere istanziata direttamente."""
        with pytest.raises(TypeError):
            WorkerBase()

    def test_concrete_subclass_must_implement_process(self):
        """Una sottoclasse che non implementa process() non è istanziabile."""
        class IncompleteWorker(WorkerBase):
            pass

        with pytest.raises(TypeError):
            IncompleteWorker()

    def test_concrete_subclass_is_instantiable(self):
        """Una sottoclasse che implementa process() deve essere istanziabile."""
        class ConcreteWorker(WorkerBase):
            def process(self, chunk: pd.DataFrame, metadata: dict) -> dict:
                return {"status": "ok"}

        worker = ConcreteWorker()
        assert worker is not None

    def test_process_returns_correct_value(self):
        """Il valore di ritorno di process() deve rispettare l'interfaccia."""
        class EchoWorker(WorkerBase):
            def process(self, chunk: pd.DataFrame, metadata: dict) -> dict:
                return {"status": "ok", **metadata}

        worker = EchoWorker()
        df = pd.DataFrame({"a": [1, 2]})
        result = worker.process(df, {"filename": "test.csv", "chunk_index": 0})

        assert result["status"] == "ok"
        assert result["filename"] == "test.csv"
