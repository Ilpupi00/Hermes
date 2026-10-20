"""
Route API per la gestione dei modelli AI in Hermes.

Endpoints:
  GET    /api/models              → lista tutti i modelli
  POST   /api/models              → crea un modello
  PUT    /api/models/{id}         → aggiorna un modello
  DELETE /api/models/{id}         → elimina un modello
  GET    /api/models/search       → cerca su HuggingFace Hub API
  POST   /api/models/{id}/test    → testa la connessione al modello
  GET    /api/models/{id}/pool    → restituisce il pool assegnato al modello
  POST   /api/models/{id}/assign-pool → assegna il modello a un pool
"""

import requests as http_requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from huggingface_hub import InferenceClient
import openai

from ...db.db import SessionLocal
from ...db import repository
from ...core import config
from ... import main as hermes_main

router = APIRouter(prefix="/api/models")

TIPOS_VALIDI = {"hf_api", "local_url", "hf_local"}

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class ModelCreate(BaseModel):
    nome_modello: str  = Field(..., min_length=1, max_length=100)
    tipo:         str  = Field(default="hf_api")
    endpoint_url: Optional[str] = Field(default=None, max_length=500)
    descrizione:  Optional[str] = Field(default=None)

class ModelUpdate(BaseModel):
    nome_modello: Optional[str] = Field(default=None, min_length=1, max_length=100)
    tipo:         Optional[str] = Field(default=None)
    endpoint_url: Optional[str] = Field(default=None, max_length=500)
    descrizione:  Optional[str] = Field(default=None)

class TestModelRequest(BaseModel):
    hub_token:    Optional[str] = Field(default=None)
    prompt:       str           = Field(default="Ciao! Rispondi con una parola sola.")
    max_tokens:   int           = Field(default=50, ge=1, le=500)

class AssignPoolRequest(BaseModel):
    pool_name: Optional[str] = Field(default=None, description="Nome del pool. Null per rimuovere l'assegnazione.")

# ─────────────────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_models():
    """Restituisce tutti i modelli registrati nel DB."""
    with SessionLocal() as db:
        models = repository.get_all_models(db)
        return {
            "models": [
                {
                    "id_modello":   m.id_modello,
                    "nome_modello": m.nome_modello,
                    "tipo":         m.tipo,
                    "endpoint_url": m.endpoint_url,
                    "descrizione":  m.descrizione,
                }
                for m in models
            ]
        }


@router.post("")
async def create_model(params: ModelCreate):
    """Crea un nuovo modello."""
    if params.tipo not in TIPOS_VALIDI:
        raise HTTPException(status_code=400, detail=f"tipo deve essere uno di: {TIPOS_VALIDI}")
    if params.tipo == "local_url" and not params.endpoint_url:
        raise HTTPException(status_code=400, detail="endpoint_url è obbligatorio per tipo=local_url")

    with SessionLocal() as db:
        modello = repository.create_model(
            db,
            nome_modello=params.nome_modello,
            tipo=params.tipo,
            endpoint_url=params.endpoint_url,
            descrizione=params.descrizione,
        )
        db.commit()
        return {
            "success":    True,
            "id_modello": modello.id_modello,
            "nome_modello": modello.nome_modello,
        }


@router.put("/{id_modello}")
async def update_model(id_modello: int, params: ModelUpdate):
    """Aggiorna un modello esistente."""
    if params.tipo and params.tipo not in TIPOS_VALIDI:
        raise HTTPException(status_code=400, detail=f"tipo deve essere uno di: {TIPOS_VALIDI}")

    with SessionLocal() as db:
        modello = repository.update_model(
            db,
            id_modello=id_modello,
            nome_modello=params.nome_modello,
            tipo=params.tipo,
            endpoint_url=params.endpoint_url,
            descrizione=params.descrizione,
        )
        if not modello:
            raise HTTPException(status_code=404, detail="Modello non trovato")
        db.commit()
        return {"success": True, "id_modello": modello.id_modello}


@router.delete("/{id_modello}")
async def delete_model(id_modello: int):
    """Elimina un modello."""
    with SessionLocal() as db:
        deleted = repository.delete_model(db, id_modello)
        if not deleted:
            raise HTTPException(status_code=404, detail="Modello non trovato")
        db.commit()
        return {"success": True}

@router.post("/{id_modello}/preload")
def preload_local_model(id_modello: int):
    """Precarica un modello hf_local in cache (sincrono, può richiedere minuti)."""
    with SessionLocal() as db:
        modello = repository.get_model_by_id(db, id_modello)
        if not modello:
            raise HTTPException(status_code=404, detail="Modello non trovato")
        
        if modello.tipo != "hf_local":
            raise HTTPException(status_code=400, detail="Solo i modelli hf_local possono essere precaricati")
            
        if not hermes_main.dispatcher or not hermes_main.dispatcher.worker:
            raise HTTPException(status_code=503, detail="Il motore Hermes non è avviato. Avvia il sistema prima di precaricare.")
            
        success = hermes_main.dispatcher.worker.preload_model(modello.nome_modello)
        if success:
            return {"success": True, "message": f"Modello '{modello.nome_modello}' precaricato con successo."}
        else:
            raise HTTPException(status_code=500, detail="Errore durante il precaricamento. Controlla i log di sistema.")

# ─────────────────────────────────────────────────────────────────────────────
# Ricerca HuggingFace Hub
# ─────────────────────────────────────────────────────────────────────────────

HF_API_SEARCH = "https://huggingface.co/api/models"

@router.get("/search")
async def search_huggingface(
    q:     str = "",
    limit: int = 12,
    task:  str = "",   # es. text-generation, text2text-generation, conversational
):
    """
    Cerca modelli su HuggingFace Hub.
    Restituisce una lista di modelli con id, task, likes, downloads e tags.
    """
    params: dict = {
        "search":     q,
        "limit":      min(limit, 50),
        "sort":       "downloads",
        "direction":  -1,
        "full":       False,
        "config":     False,
    }
    # Filtro per pipeline_tag (task)
    if task:
        params["pipeline_tag"] = task
    else:
        # Di default mostriamo solo i modelli di generazione testo
        params["pipeline_tag"] = "text-generation"

    headers = {}
    if config.HF_TOKEN:
        headers["Authorization"] = f"Bearer {config.HF_TOKEN}"

    try:
        resp = http_requests.get(HF_API_SEARCH, params=params, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        results = [
            {
                "id":          m.get("id", ""),
                "pipeline":    m.get("pipeline_tag", ""),
                "likes":       m.get("likes", 0),
                "downloads":   m.get("downloads", 0),
                "tags":        m.get("tags", [])[:6],
                "private":     m.get("private", False),
            }
            for m in data
        ]
        return {"results": results, "total": len(results)}

    except http_requests.Timeout:
        raise HTTPException(status_code=504, detail="HuggingFace API timeout")
    except http_requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"HuggingFace API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────────────────
# Test connessione modello
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{id_modello}/test")
async def test_model(id_modello: int, params: TestModelRequest):
    """
    Testa la connessione al modello inviando un prompt di prova.
    Restituisce status='ok' + la risposta del modello, oppure status='error'.
    """
    with SessionLocal() as db:
        modello = repository.get_model_by_id(db, id_modello)
        if not modello:
            raise HTTPException(status_code=404, detail="Modello non trovato")

        tipo         = modello.tipo
        nome_modello = modello.nome_modello
        endpoint_url = modello.endpoint_url

    try:
        if tipo == "hf_api":
            token = params.hub_token or config.HF_TOKEN
            if not token:
                return {"status": "error", "detail": "hub_token obbligatorio per tipo=hf_api (oppure configura HF_TOKEN in .env)"}
            client = InferenceClient(
                provider=config.HF_INFERENCE_PROVIDER,
                api_key=token,
            )
            try:
                response = client.chat.completions.create(
                    model=nome_modello,
                    messages=[{"role": "user", "content": params.prompt}],
                    max_tokens=params.max_tokens,
                    temperature=0.1,
                )
                risposta = response.choices[0].message.content or ""
            except Exception as e:
                err_str = str(e).lower()
                if "model_not_supported" in err_str or "not supported by any provider" in err_str:
                    return {
                        "status": "error",
                        "detail": (
                            "Questo modello non è disponibile tramite i provider "
                            "Hugging Face abilitati per il tuo account. Abilita un "
                            "provider compatibile nelle impostazioni Inference "
                            "Providers, seleziona un altro modello oppure usa "
                            "l'esecuzione locale."
                        ),
                    }
                else:
                    return {"status": "error", "detail": str(e)}
            
            return {"status": "ok", "risposta": risposta, "modello": nome_modello, "tipo": tipo}

        elif tipo == "local_url":
            if not endpoint_url:
                return {"status": "error", "detail": "L'URL endpoint locale è obbligatorio"}
            client = openai.OpenAI(base_url=endpoint_url, api_key="not-needed")
            try:
                resp = client.chat.completions.create(
                    model=nome_modello,
                    messages=[{"role": "user", "content": params.prompt}],
                    temperature=0.1,
                    max_tokens=params.max_tokens,
                )
                risposta = resp.choices[0].message.content or ""
                return {"status": "ok", "risposta": risposta, "modello": nome_modello, "tipo": tipo}
            except Exception as e:
                return {"status": "error", "detail": f"Errore connessione a server locale: {str(e)}"}
                
        elif tipo == "hf_local":
            import asyncio
            import torch
            from transformers import pipeline
            
            def run_local_hf_test():
                device = "cuda" if torch.cuda.is_available() else "cpu"
                dtype = torch.float16 if device == "cuda" else torch.float32
                pipe = pipeline(
                    "text-generation", 
                    model=nome_modello, 
                    torch_dtype=dtype,
                    device_map="auto" if device == "cuda" else None
                )
                result = pipe(
                    params.prompt,
                    max_new_tokens=params.max_tokens,
                    temperature=0.1,
                    do_sample=True,
                    return_full_text=False
                )
                return result[0]['generated_text'].strip()

            try:
                # Esegui in un thread separato per non bloccare uvicorn
                risposta = await asyncio.to_thread(run_local_hf_test)
                return {"status": "ok", "risposta": risposta, "modello": nome_modello, "tipo": tipo}
            except Exception as e:
                return {"status": "error", "detail": f"Errore caricamento nativo ({nome_modello}): {str(e)}. Assicurati di avere RAM/VRAM sufficiente."}

        else:
            return {"status": "error", "detail": f"tipo '{tipo}' non supportato"}

    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# Pool assignment
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{id_modello}/pool")
async def get_model_pool(id_modello: int):
    """Restituisce il pool attualmente assegnato al modello, oppure None."""
    with SessionLocal() as db:
        modello = repository.get_model_by_id(db, id_modello)
        if not modello:
            raise HTTPException(status_code=404, detail="Modello non trovato")
        nome_modello = modello.nome_modello

    if hermes_main.dispatcher:
        assigned_pool = hermes_main.dispatcher.get_route(nome_modello)
        # get_route ritorna 'default' anche se non c'è una regola esplicita
        # Verifichiamo se c'è una regola esplicita nella routing_table
        routes = hermes_main.dispatcher.get_routes()
        explicit_pool = routes.get(nome_modello)
        return {
            "nome_modello": nome_modello,
            "pool": explicit_pool,  # None se non c'è regola esplicita
            "effective_pool": assigned_pool,  # sempre valorizzato (default fallback)
            "available_pools": list(hermes_main.dispatcher.pools.keys()),
        }
    return {
        "nome_modello": nome_modello,
        "pool": None,
        "effective_pool": None,
        "available_pools": [],
    }


@router.post("/{id_modello}/assign-pool")
async def assign_model_to_pool(id_modello: int, params: AssignPoolRequest):
    """
    Assegna il modello a un pool del dispatcher.
    Se pool_name è None o stringa vuota, rimuove l'assegnazione (usa il default).
    """
    with SessionLocal() as db:
        modello = repository.get_model_by_id(db, id_modello)
        if not modello:
            raise HTTPException(status_code=404, detail="Modello non trovato")
        nome_modello = modello.nome_modello

    if not hermes_main.dispatcher:
        return {"success": False, "message": "Hermes non avviato. Avvia il motore prima di assegnare un pool."}

    pool_name = params.pool_name

    if not pool_name:
        # Rimuovi assegnazione esplicita (tornerà al default)
        hermes_main.dispatcher.delete_route(nome_modello)
        return {"success": True, "message": f"❌ Assegnazione rimossa — '{nome_modello}' userà il pool default", "pool": None}

    # Verifica che il pool esista
    available = list(hermes_main.dispatcher.pools.keys())
    if pool_name not in available:
        return {"success": False, "message": f"Pool '{pool_name}' non trovato. Pool disponibili: {available}"}

    hermes_main.dispatcher.set_route(nome_modello, pool_name)
    return {"success": True, "message": f"✓ '{nome_modello}' assegnato al pool '{pool_name}'", "pool": pool_name}
