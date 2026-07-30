from datetime import UTC, datetime
import json

from sqlalchemy.orm import Session
from .models import (
    Esecuzione,
    FileCSV,
    ModelloLLM,
    RigaInput,
    Risultato,
    Task,
    Utente,
)
from .status import JobStatus

# ─────────────────────────────────────────────────────────────────────────────
# Execution context (usato dal HybridWorker)
# ─────────────────────────────────────────────────────────────────────────────

def get_execution_context(db: Session, id_esecuzione: int) -> dict:
    result = (
        db.query(
            Utente.hub_token,
            Task.prompt,
            ModelloLLM.nome_modello,
            ModelloLLM.tipo,
            ModelloLLM.endpoint_url,
            Task.temperatura,
            Task.max_tokens,
            Esecuzione.id_file,
        )
        .select_from(Esecuzione)
        .join(Task, Esecuzione.id_task == Task.id_task)
        .join(Utente, Task.id_utente == Utente.id_utente)
        .join(ModelloLLM, Task.id_modello == ModelloLLM.id_modello)
        .filter(Esecuzione.id_esecuzione == id_esecuzione)
        .first()
    )

    if not result:
        raise ValueError(f"Esecuzione {id_esecuzione} non trovata.")

    return {
        "hub_token":    result.hub_token,
        "prompt":       result.prompt,
        "nome_modello": result.nome_modello,
        "tipo":         result.tipo if result.tipo else "hf_api",
        "endpoint_url": result.endpoint_url,
        "temperatura":  result.temperatura if result.temperatura is not None else 0.1,
        "max_tokens":   result.max_tokens  if result.max_tokens  is not None else 500,
        "id_file":      result.id_file,
    }


def create_input_file(
    db: Session,
    nome_file: str,
    rows: list[dict[str, str | None]],
) -> FileCSV:
    """Registra il CSV e le sue righe, restituendo il record del file."""
    file_csv = FileCSV(nome_file=nome_file, numero_righe=len(rows))
    db.add(file_csv)
    db.flush()

    db.add_all(
        RigaInput(
            id_file=file_csv.id_file,
            indice_riga=index,
            contenuto=json.dumps(row, ensure_ascii=False),
        )
        for index, row in enumerate(rows)
    )
    db.flush()
    return file_csv


def get_input_row_ids(
    db: Session,
    id_file: int,
    row_indexes: list[int],
) -> dict[int, int]:
    """Restituisce la corrispondenza indice CSV → chiave della riga persistita."""
    if not row_indexes:
        return {}

    rows = (
        db.query(RigaInput.indice_riga, RigaInput.id_riga_input)
        .filter(
            RigaInput.id_file == id_file,
            RigaInput.indice_riga.in_(row_indexes),
        )
        .all()
    )
    result = {int(row.indice_riga): int(row.id_riga_input) for row in rows}
    missing = sorted(set(row_indexes) - result.keys())
    if missing:
        raise ValueError(
            f"Righe input mancanti per file {id_file}: {missing}"
        )
    return result


def save_result(db: Session, id_esecuzione: int, id_file: int, id_riga_input: int, output: str, tempo_esecuzione: float, stato: str):
    nuovo_risultato = Risultato(
        id_esecuzione=id_esecuzione,
        id_file=id_file,
        id_riga_input=id_riga_input,
        output=output,
        tempo_esecuzione=tempo_esecuzione,
        stato=stato
    )
    db.add(nuovo_risultato)
    db.flush()

def set_task_status_by_execution(db: Session, id_esecuzione: int, stato: str):
    target_status = JobStatus(stato)
    esecuzione = db.query(Esecuzione).filter(Esecuzione.id_esecuzione == id_esecuzione).first()
    if esecuzione:
        esecuzione.stato = target_status.value
        if target_status == JobStatus.RUNNING and esecuzione.data_inizio is None:
            esecuzione.data_inizio = datetime.now(UTC).replace(tzinfo=None)
        if target_status in {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }:
            esecuzione.data_fine = datetime.now(UTC).replace(tzinfo=None)

        task = db.query(Task).filter(Task.id_task == esecuzione.id_task).first()
        if task:
            task.stato = target_status.value
            db.flush()

# ─────────────────────────────────────────────────────────────────────────────
# CRUD modelli (usato dalla GUI)
# ─────────────────────────────────────────────────────────────────────────────

def get_all_models(db: Session) -> list[ModelloLLM]:
    """Restituisce tutti i modelli registrati."""
    return db.query(ModelloLLM).order_by(ModelloLLM.id_modello).all()

def get_model_by_id(db: Session, id_modello: int) -> ModelloLLM | None:
    """Restituisce un modello per ID, o None se non esiste."""
    return db.query(ModelloLLM).filter(ModelloLLM.id_modello == id_modello).first()

def create_model(
    db: Session,
    nome_modello: str,
    tipo: str = "hf_api",
    endpoint_url: str | None = None,
    descrizione: str | None = None,
) -> ModelloLLM:
    """Crea e persiste un nuovo ModelloLLM."""
    modello = ModelloLLM(
        nome_modello=nome_modello,
        tipo=tipo,
        endpoint_url=endpoint_url,
        descrizione=descrizione,
    )
    db.add(modello)
    db.flush()
    return modello

def update_model(
    db: Session,
    id_modello: int,
    nome_modello: str | None = None,
    tipo: str | None = None,
    endpoint_url: str | None = None,
    descrizione: str | None = None,
) -> ModelloLLM | None:
    """Aggiorna i campi di un ModelloLLM esistente. Restituisce None se non trovato."""
    modello = get_model_by_id(db, id_modello)
    if not modello:
        return None
    if nome_modello  is not None: modello.nome_modello  = nome_modello
    if tipo          is not None: modello.tipo          = tipo
    if endpoint_url  is not None: modello.endpoint_url  = endpoint_url
    if descrizione   is not None: modello.descrizione   = descrizione
    db.flush()
    return modello

def delete_model(db: Session, id_modello: int) -> bool:
    """Elimina un ModelloLLM per ID. Restituisce True se eliminato, False se non trovato."""
    modello = get_model_by_id(db, id_modello)
    if not modello:
        return False
    db.delete(modello)
    db.flush()
    return True
