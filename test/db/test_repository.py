"""
Test unitari per src/db/repository.py

Copre:
- get_execution_context: successo, risultato None (ValueError), valori di default
- save_result: creazione e flush del record Risultato
"""
import pytest
from src.db.repository import (
    get_execution_context,
    save_result,
    set_task_status_by_execution,
)
from src.db.models import Utente, ModelloLLM, Task, Esecuzione, Risultato
from src.db.status import JobStatus


# ---------------------------------------------------------------------------
# Helpers per popolare il DB
# ---------------------------------------------------------------------------

def _create_full_context(session, *, temperatura=0.7, max_tokens=200):
    """Inserisce utente, modello, task ed esecuzione e restituisce l'id_esecuzione."""
    utente = Utente(
        username="test-user",
        email="test-user@hermes.local",
        password="test-password",
        hub_token="hf_test_token",
    )
    session.add(utente)
    session.flush()

    modello = ModelloLLM(nome_modello="mistral-7b")
    session.add(modello)
    session.flush()

    task = Task(
        id_utente=utente.id_utente,
        id_modello=modello.id_modello,
        nome="TestTask",
        prompt="Analizza i dati seguenti:",
        temperatura=temperatura,
        max_tokens=max_tokens,
    )
    session.add(task)
    session.flush()

    esecuzione = Esecuzione(id_task=task.id_task)
    session.add(esecuzione)
    session.flush()

    return esecuzione.id_esecuzione


# ---------------------------------------------------------------------------
# Test: get_execution_context
# ---------------------------------------------------------------------------

class TestGetExecutionContext:
    def test_returns_correct_fields(self, db_session):
        """Il dizionario restituito contiene tutte le chiavi attese."""
        id_exec = _create_full_context(db_session, temperatura=0.3, max_tokens=512)

        ctx = get_execution_context(db_session, id_exec)

        assert ctx["hub_token"] == "hf_test_token"
        assert ctx["prompt"] == "Analizza i dati seguenti:"
        assert ctx["nome_modello"] == "mistral-7b"
        assert ctx["temperatura"] == pytest.approx(0.3)
        assert ctx["max_tokens"] == 512

    def test_raises_for_nonexistent_execution(self, db_session):
        """Se l'id_esecuzione non esiste, deve sollevare ValueError."""
        with pytest.raises(ValueError, match="non trovata"):
            get_execution_context(db_session, id_esecuzione=99999)

    def test_default_temperatura_when_none(self, db_session):
        """Se temperatura è None nel DB, il context restituisce il default 0.1."""
        id_exec = _create_full_context(db_session, temperatura=None, max_tokens=100)

        ctx = get_execution_context(db_session, id_exec)

        assert ctx["temperatura"] == pytest.approx(0.1)

    def test_default_max_tokens_when_none(self, db_session):
        """Se max_tokens è None nel DB, il context restituisce il default 500."""
        id_exec = _create_full_context(db_session, temperatura=0.5, max_tokens=None)

        ctx = get_execution_context(db_session, id_exec)

        assert ctx["max_tokens"] == 500

    def test_returns_dict_type(self, db_session):
        """Il valore restituito è sempre un dizionario."""
        id_exec = _create_full_context(db_session)

        result = get_execution_context(db_session, id_exec)

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Test: save_result
# ---------------------------------------------------------------------------

class TestSaveResult:
    def _setup_execution(self, session):
        """Crea un'esecuzione minima per testare save_result."""
        return _create_full_context(session)

    def test_record_is_flushed_to_session(self, db_session):
        """Dopo save_result, il Risultato deve essere presente nella sessione."""
        id_exec = self._setup_execution(db_session)

        save_result(
            db=db_session,
            id_esecuzione=id_exec,
            id_file=1,
            id_riga_input=42,
            output="risposta AI",
            tempo_esecuzione=1.23,
            stato="Completato",
        )

        risultato = db_session.query(Risultato).filter_by(id_esecuzione=id_exec).first()
        assert risultato is not None

    def test_record_fields_are_correct(self, db_session):
        """I campi del Risultato devono corrispondere ai parametri passati."""
        id_exec = self._setup_execution(db_session)

        save_result(
            db=db_session,
            id_esecuzione=id_exec,
            id_file=7,
            id_riga_input=99,
            output="output di test",
            tempo_esecuzione=2.50,
            stato="Completato",
        )

        ris = db_session.query(Risultato).filter_by(id_esecuzione=id_exec).first()
        assert ris.id_file == 7
        assert ris.id_riga_input == 99
        assert ris.output == "output di test"
        assert ris.tempo_esecuzione == pytest.approx(2.50)
        assert ris.stato == "Completato"

    def test_record_stato_errore(self, db_session):
        """save_result funziona correttamente anche con stato 'Errore'."""
        id_exec = self._setup_execution(db_session)

        save_result(
            db=db_session,
            id_esecuzione=id_exec,
            id_file=1,
            id_riga_input=1,
            output="timeout",
            tempo_esecuzione=0.0,
            stato="Errore",
        )

        ris = db_session.query(Risultato).filter_by(id_esecuzione=id_exec).first()
        assert ris.stato == "Errore"

    def test_multiple_results_for_same_execution(self, db_session):
        """È possibile salvare più risultati per la stessa esecuzione."""
        id_exec = self._setup_execution(db_session)

        for i in range(3):
            save_result(
                db=db_session,
                id_esecuzione=id_exec,
                id_file=1,
                id_riga_input=i,
                output=f"output_{i}",
                tempo_esecuzione=float(i),
                stato="Completato",
            )

        count = db_session.query(Risultato).filter_by(id_esecuzione=id_exec).count()
        assert count == 3


class TestSetExecutionStatus:
    def test_updates_task_and_execution(self, db_session):
        id_exec = _create_full_context(db_session)

        set_task_status_by_execution(
            db_session, id_exec, JobStatus.RUNNING.value
        )

        execution = db_session.get(Esecuzione, id_exec)
        task = db_session.get(Task, execution.id_task)
        assert execution.stato == JobStatus.RUNNING.value
        assert task.stato == JobStatus.RUNNING.value
        assert execution.data_inizio is not None

    def test_terminal_status_sets_end_time(self, db_session):
        id_exec = _create_full_context(db_session)

        set_task_status_by_execution(
            db_session, id_exec, JobStatus.COMPLETED.value
        )

        execution = db_session.get(Esecuzione, id_exec)
        assert execution.data_fine is not None

    def test_rejects_unknown_status(self, db_session):
        id_exec = _create_full_context(db_session)

        with pytest.raises(ValueError):
            set_task_status_by_execution(db_session, id_exec, "Sconosciuto")
