"""
Route API per l'upload e l'esecuzione di job CSV in Hermes.

Endpoints:
  POST /api/upload           → carica un CSV, crea Task+Esecuzione, deposita in INBOX
  GET  /api/jobs             → lista tutte le esecuzioni con stato aggregato
  GET  /api/jobs/{id}/results → risultati di una esecuzione specifica (paginati)
"""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import io, csv as csv_mod

from ...db.db import SessionLocal
from ...db import repository
from ...db.models import Utente, Task, Esecuzione, Risultato, ModelloLLM
from ...db.status import JobStatus, ResultStatus
from ...core import config
from ... import main as hermes_main

router = APIRouter(prefix="/api")

# ─────────────────────────────────────────────────────────────────────────────
# Helper: utente default
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_default_user(db) -> Utente:
    """Recupera o crea l'utente di default."""
    utente = db.query(Utente).first()
    if not utente:
        utente = Utente(
            username="hermes",
            email="hermes@localhost",
            password="fake_password",
            hub_token=config.HF_TOKEN or ""
        )
        db.add(utente)
        db.flush()
    return utente


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/upload — Carica CSV e avvia job
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_csv(
    file:        UploadFile  = File(...),
    id_modello:  int         = Form(...),
    prompt:      str         = Form(...),
    temperatura: float       = Form(0.1),
    max_tokens:  int         = Form(500),
    hub_token:   Optional[str] = Form(None),
    chunk_size:  int         = Form(1000),
):
    """
    Carica un CSV nella INBOX di Hermes creando i record DB necessari.
    Il file viene rinominato secondo la convention:
        job_{id_esecuzione}_file_{id_file}.csv
    """

    # ── Validazione preliminare ───────────────────────────────────────────────
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Il file deve essere un CSV (.csv)")

    # ── Leggi contenuto CSV ───────────────────────────────────────────────
    content = await file.read()

    # Verifica che sia CSV leggibile e conta le righe
    try:
        decoded = content.decode("utf-8-sig")
        reader = csv_mod.DictReader(io.StringIO(decoded))
        if not reader.fieldnames:
            raise ValueError("intestazione CSV mancante")
        rows = list(reader)
        n_righe = len(rows)
        
        # ── Auto-tuning del chunk_size per parallelismo ottimale ──
        num_workers = config.MAX_WORKERS
        if num_workers > 0 and n_righe > 0:
            optimal_chunk = max(1, n_righe // (num_workers * 2))
            if optimal_chunk < chunk_size:
                config.logger.info(f"Auto-tuning chunk_size da {chunk_size} a {optimal_chunk} per massimizzare parallelismo (righe={n_righe}, workers={num_workers})")
                chunk_size = optimal_chunk

    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"CSV non valido o non decodificabile: {str(e)}"
        )

    if n_righe == 0:
        raise HTTPException(
            status_code=422,
            detail="Il CSV è vuoto o ha solo l'intestazione"
        )

    with SessionLocal() as db:
        # Verifica modello
        modello = repository.get_model_by_id(db, id_modello)
        if not modello:
            raise HTTPException(status_code=404, detail=f"Modello {id_modello} non trovato")

        # Crea / recupera utente default
        utente = _get_or_create_default_user(db)

        # Aggiorna hub_token se fornito
        if hub_token:
            utente.hub_token = hub_token
            db.flush()

        # ── Pre-flight validation su HuggingFace ─────────────────────────────
        token_to_use = utente.hub_token
        if modello.tipo == "hf_api" and not token_to_use:
            raise HTTPException(status_code=401, detail="Token HuggingFace richiesto per l'Inference API ma non fornito.")
        
        if modello.tipo in ("hf_api", "hf_local"):
            import requests
            headers = {}
            if token_to_use:
                headers["Authorization"] = f"Bearer {token_to_use}"
            
            hf_url = f"https://huggingface.co/api/models/{modello.nome_modello}"
            try:
                resp = requests.get(hf_url, headers=headers, timeout=5)
                if resp.status_code == 401:
                    raise HTTPException(status_code=401, detail="Il token HuggingFace fornito non è valido.")
                elif resp.status_code == 403:
                    raise HTTPException(status_code=403, detail=f"Accesso negato a '{modello.nome_modello}'. È un modello protetto (Gated)? Verifica su HF.")
                elif resp.status_code == 404:
                    raise HTTPException(status_code=404, detail=f"Il modello '{modello.nome_modello}' non esiste o il tuo token non ha i permessi per vederlo.")
            except requests.RequestException as e:
                config.logger.warning(f"Impossibile verificare il modello su HF: {e}")

        # Registra il file e le righe prima di creare l'esecuzione.
        file_csv = repository.create_input_file(db, file.filename, rows)

        # Crea Task
        task = Task(
            id_utente=utente.id_utente,
            id_modello=id_modello,
            nome=f"Upload {file.filename[:50]}",
            stato=JobStatus.QUEUED.value,
            prompt=prompt,
            temperatura=temperatura,
            max_tokens=max_tokens,
        )
        db.add(task)
        db.flush()

        # Crea Esecuzione
        esecuzione = Esecuzione(
            id_task=task.id_task,
            id_file=file_csv.id_file,
            stato=JobStatus.QUEUED.value,
            totale_righe=n_righe,
        )
        db.add(esecuzione)
        db.flush()

        id_esecuzione = esecuzione.id_esecuzione
        id_file = file_csv.id_file

        # ── Salva in INBOX con naming convention ─────────────────────────────
        config.init_directories()
        dest_name = f"job_{id_esecuzione}_file_{id_file}.csv"
        dest_path = config.INBOX / dest_name

        try:
            dest_path.write_bytes(content)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Impossibile salvare il file in INBOX: {str(e)}"
            )

        db.commit()

        config.logger.info(
            f"[UPLOAD] file={dest_name} esecuzione={id_esecuzione} "
            f"task={task.id_task} modello={modello.nome_modello} righe={n_righe} "
            f"chunk_size={chunk_size} status=deposited_in_INBOX"
        )

        return {
            "success":      True,
            "id_esecuzione": id_esecuzione,
            "id_task":      task.id_task,
            "id_file":      id_file,
            "filename":     dest_name,
            "n_righe":      n_righe,
            "modello":      modello.nome_modello,
            "tipo":         modello.tipo,
            "message":      (
                f"File '{dest_name}' depositato in INBOX con {n_righe} righe. "
                f"Hermes lo elaborerà al prossimo ciclo di polling."
                if hermes_main.dispatcher
                else "⚠️ Hermes non è avviato — avvia il motore per elaborare il file."
            ),
            "hermes_running": hermes_main.dispatcher is not None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/jobs — Lista esecuzioni con stato aggregato
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs():
    """Restituisce tutte le esecuzioni con contatori di risultati (ok/errori/totale)."""
    with SessionLocal() as db:
        rows = (
            db.query(
                Esecuzione.id_esecuzione,
                Esecuzione.totale_righe,
                Task.nome,
                Task.stato,
                Task.prompt,
                ModelloLLM.nome_modello,
                ModelloLLM.tipo,
            )
            .join(Task,      Esecuzione.id_task    == Task.id_task)
            .join(ModelloLLM, Task.id_modello      == ModelloLLM.id_modello)
            .order_by(Esecuzione.id_esecuzione.desc())
            .limit(50)
            .all()
        )

        jobs = []
        for r in rows:
            # Usa il totale_righe salvato all'upload per calcolare la percentuale corretta
            totale = r.totale_righe or 0
            
            completate = db.query(Risultato).filter(
                Risultato.id_esecuzione == r.id_esecuzione,
                Risultato.stato == ResultStatus.COMPLETED.value
            ).count()
            
            errori = db.query(Risultato).filter(
                Risultato.id_esecuzione == r.id_esecuzione,
                Risultato.stato != ResultStatus.COMPLETED.value
            ).count()

            jobs.append({
                "id_esecuzione": r.id_esecuzione,
                "nome":         r.nome,
                "stato":        r.stato,
                "modello":      r.nome_modello,
                "tipo":         r.tipo,
                "totale":       totale,
                "completate":   completate,
                "errori":       errori,
            })

        return {"jobs": jobs}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/jobs/{id_esecuzione}/results — Risultati di una esecuzione
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/jobs/{job_id}")
def delete_job(job_id: int):
    """Elimina definitivamente un job (Task, Esecuzione, Risultati) dal database e ferma l'elaborazione se in corso."""
    
    # 1. Se il job è attualmente in elaborazione, mandiamo il segnale di aborto ai thread
    if hasattr(hermes_main, "active_cancel_events"):
        cancel_event = hermes_main.active_cancel_events.get(job_id)
        if cancel_event:
            cancel_event.set()
            config.logger.warning(f"status=JOB_CANCELLED job_id={job_id} Segnale di terminazione forzata inviato.")

    with SessionLocal() as db:
        esecuzione = db.query(Esecuzione).filter(Esecuzione.id_esecuzione == job_id).first()
        if not esecuzione:
            raise HTTPException(status_code=404, detail="Job non trovato")
        
        try:
            # 1. Elimina risultati
            db.query(Risultato).filter(Risultato.id_esecuzione == job_id).delete(synchronize_session=False)
            # 2. Elimina esecuzione
            task_id = esecuzione.id_task
            db.query(Esecuzione).filter(Esecuzione.id_esecuzione == job_id).delete(synchronize_session=False)
            # 3. Elimina task
            if task_id:
                db.query(Task).filter(Task.id_task == task_id).delete(synchronize_session=False)
            
            db.commit()
            return {"status": "ok", "message": "Job eliminato"}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Errore durante l'eliminazione: {str(e)}")

@router.get("/jobs/{id_esecuzione}/results")
async def get_job_results(id_esecuzione: int, limit: int = 200, offset: int = 0):
    """Ritorna i risultati paginati di un'esecuzione."""
    with SessionLocal() as db:
        esec = db.query(Esecuzione).filter(
            Esecuzione.id_esecuzione == id_esecuzione
        ).first()
        if not esec:
            raise HTTPException(status_code=404, detail="Esecuzione non trovata")

        risultati = (
            db.query(Risultato)
            .filter(Risultato.id_esecuzione == id_esecuzione)
            .order_by(Risultato.id_riga_input)
            .offset(offset)
            .limit(limit)
            .all()
        )

        totale = db.query(Risultato).filter(
            Risultato.id_esecuzione == id_esecuzione
        ).count()

        return {
            "id_esecuzione": id_esecuzione,
            "totale":        totale,
            "offset":        offset,
            "limit":         limit,
            "results": [
                {
                    "id_riga_input":     r.id_riga_input,
                    "id_file":           r.id_file,
                    "output":            r.output,
                    "tempo_esecuzione":  r.tempo_esecuzione,
                    "stato":             r.stato,
                }
                for r in risultati
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/jobs/{id_esecuzione}/download — Download risultati come CSV
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/jobs/{id_esecuzione}/download")
async def download_job_results(id_esecuzione: int):
    """Scarica tutti i risultati di un'esecuzione come CSV."""
    with SessionLocal() as db:
        esec = db.query(Esecuzione).filter(
            Esecuzione.id_esecuzione == id_esecuzione
        ).first()
        if not esec:
            raise HTTPException(status_code=404, detail="Esecuzione non trovata")

        risultati = (
            db.query(Risultato)
            .filter(Risultato.id_esecuzione == id_esecuzione)
            .order_by(Risultato.id_riga_input)
            .all()
        )

        # Costruisce CSV in memoria
        output = io.StringIO()
        writer = csv_mod.writer(output)
        writer.writerow(["id_riga_input", "id_file", "stato", "tempo_esecuzione_s", "output"])
        for r in risultati:
            writer.writerow([
                r.id_riga_input,
                r.id_file,
                r.stato,
                r.tempo_esecuzione,
                r.output,
            ])

        output.seek(0)
        filename = f"hermes_results_{id_esecuzione}.csv"
        return StreamingResponse(
            io.BytesIO(output.read().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
