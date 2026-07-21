"""
HybridWorker — Worker ibrido per Hermes

Supporta due modalità di inferenza AI selezionate dinamicamente
dal campo `tipo` della tabella `modellillm`:

  hf_api    → HuggingFace Inference API (remote)
               Usa InferenceClient con hub_token e nome_modello.
               
  local_url → Server OpenAI-compatible locale (vLLM, Ollama, LM Studio, ecc.)
               Usa openai.OpenAI(base_url=endpoint_url) con api_key fissa.
               In questo caso hub_token non è necessario.
"""

import time
import threading
import logging
import pandas as pd
import requests
import tenacity
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError
import openai

from ..core import config
from ..db.db import SessionLocal
from ..db import repository
from .worker_base import WorkerBase, FatalWorkerError


class HybridWorker(WorkerBase):
    """
    Worker che supporta sia HuggingFace Inference API (remota)
    sia server locali OpenAI-compatible (vLLM, Ollama, LM Studio…).
    
    Il campo `tipo` in `modellillm` determina la strategia:
      - 'hf_api'    → usa _call_hf_api()
      - 'local_url' → usa _call_local_api()
    """

    # Cache token HF (class-level, condivisa tra istanze)
    _validated_tokens: dict[str, bool] = {}
    _token_lock = threading.Lock()
    
    # Cache per pipeline Transformers (esecuzione nativa)
    _local_pipelines = {}
    _pipeline_lock = threading.Lock()

    # ──────────────────────────────────────────────────────────────────────────
    # Entry point principale
    # ──────────────────────────────────────────────────────────────────────────

    def preload_model(self, modello: str) -> bool:
        """Forza il download e il caricamento del modello HF locale in RAM/VRAM."""
        config.logger.info(f"[HybridWorker] Pre-caricamento forzato richiesto per '{modello}'...")
        with self._pipeline_lock:
            if modello in self._local_pipelines:
                config.logger.info(f"[HybridWorker] Il modello '{modello}' è già in cache.")
                return True
            try:
                from transformers import pipeline
                pipe = pipeline(
                    "text-generation", 
                    model=modello, 
                    device_map="auto"
                )
                self._local_pipelines[modello] = pipe
                config.logger.info(f"[HybridWorker] Pre-caricamento di '{modello}' completato con successo.")
                return True
            except Exception as e:
                config.logger.error(f"[HybridWorker] Errore nel pre-caricamento di '{modello}': {str(e)}")
                return False

    def process(self, chunk: pd.DataFrame, metadata: dict) -> dict:
        filename    = metadata.get("filename", "")
        chunk_index = metadata.get("chunk_index", 0)
        n_righe     = len(chunk)

        # 1. Parsing del nome file → id_esecuzione, id_file
        try:
            parts         = filename.split("_")
            id_esecuzione = int(parts[1])
            id_file       = int(parts[3].split(".")[0])
        except Exception:
            raise FatalWorkerError(f"Nome file non valido: {filename}")

        # 2. Recupero contesto dal DB
        with SessionLocal() as db:
            try:
                context = repository.get_execution_context(db, id_esecuzione)
            except Exception as e:
                raise FatalWorkerError(f"Errore DB: {str(e)}")

            tipo         = context["tipo"]
            endpoint_url = context["endpoint_url"]
            modello      = context["nome_modello"]
            prompt_base  = context["prompt"]
            temperatura  = context["temperatura"]
            max_tokens   = context["max_tokens"]

            token_db = context.get("hub_token")
            token    = token_db if token_db else getattr(config, "HF_TOKEN", "")

            # ── Log: inizio chunk ────────────────────────────────────────────
            config.logger.info(
                f"[AI] chunk={chunk_index} esecuzione={id_esecuzione} file={id_file} "
                f"righe={n_righe} modello={modello} tipo={tipo} "
                f"temp={temperatura} max_tok={max_tokens}"
            )

            # --- Validazione token HF API ---
            if tipo == "hf_api":
                if not token:
                    raise FatalWorkerError(
                        "Token HuggingFace non configurato. Salvalo nel DB o in .env (HF_TOKEN)."
                    )
                if not self._is_token_valid(token):
                    raise FatalWorkerError("Token HuggingFace non valido o revocato.")

            # 4. Inizializza client appropriato
            if tipo == "hf_api":
                client  = InferenceClient(token=token)
                call_fn = lambda prompt: self._call_hf_api(
                    client, modello, prompt, temperatura, max_tokens
                )
                config.logger.info(
                    f"[AI] client=HuggingFaceAPI modello={modello} pronto"
                )
            elif tipo == "local_url":
                if not endpoint_url:
                    raise FatalWorkerError("endpoint_url mancante per il modello local_url.")
                oa_client = openai.OpenAI(base_url=endpoint_url, api_key="not-needed")
                call_fn   = lambda prompt: self._call_local_api(
                    oa_client, modello, prompt, temperatura, max_tokens
                )
                config.logger.info(
                    f"[AI] client=LocalAPI endpoint={endpoint_url} modello={modello} pronto"
                )
            elif tipo == "hf_local":
                call_fn = lambda prompt: self._call_hf_local(
                    modello, prompt, temperatura, max_tokens
                )
                config.logger.info(
                    f"[AI] client=HFTransformers modello={modello} caricamento/uso pipeline locale"
                )
            else:
                raise FatalWorkerError(f"Tipo modello sconosciuto: '{tipo}'")

            # 5. Iterazione righe del chunk
            completate = 0
            errori     = 0
            try:
                for index, row in chunk.iterrows():
                    cancel_event = metadata.get("cancel_event")
                    if cancel_event and cancel_event.is_set():
                        config.logger.warning(
                            f"[AI] chunk={chunk_index} INTERROTTO da Circuit Breaker"
                        )
                        raise FatalWorkerError(
                            "Elaborazione interrotta per attivazione Circuit Breaker."
                        )

                    id_riga   = int(row.get("id_riga_input", index))
                    dati_riga = row.drop("id_riga_input", errors='ignore').to_dict()
                    prompt_ok = f"{prompt_base}\n\nDati:\n{dati_riga}"

                    config.logger.info(
                        f"[AI] chunk={chunk_index} riga={id_riga} "
                        f"status=calling modello={modello}"
                    )

                    start_time = time.time()
                    try:
                        risposta = call_fn(prompt_ok)
                        tempo    = round(time.time() - start_time, 2)
                        repository.save_result(
                            db, id_esecuzione, id_file, id_riga,
                            risposta, tempo, "Completato"
                        )
                        db.commit()
                        completate += 1
                        config.logger.info(
                            f"[AI] chunk={chunk_index} riga={id_riga} "
                            f"status=OK tempo={tempo}s tokens_out={len(risposta.split())}"
                        )
                    except Exception as e:
                        errori += 1
                        config.logger.error(
                            f"[AI] chunk={chunk_index} riga={id_riga} "
                            f"status=ERROR reason={str(e)[:120]}"
                        )
                        repository.save_result(
                            db, id_esecuzione, id_file, id_riga, str(e), 0.0, "Errore"
                        )
                        db.commit()

                # ── Log: chunk completato ────────────────────────────────────
                config.logger.info(
                    f"[AI] chunk={chunk_index} COMPLETATO "
                    f"ok={completate} errori={errori} totale={n_righe}"
                )

            except Exception as db_err:
                db.rollback()
                if isinstance(db_err, FatalWorkerError):
                    raise
                config.logger.error(
                    f"[AI] chunk={chunk_index} COMMIT_ERROR reason={str(db_err)}"
                )
                raise FatalWorkerError(
                    f"Impossibile salvare i risultati del chunk: {str(db_err)}"
                )

        return {"status": "ok", **metadata}

    # ──────────────────────────────────────────────────────────────────────────
    # Validazione token HuggingFace (con cache e lock)
    # ──────────────────────────────────────────────────────────────────────────

    def _is_token_valid(self, token: str) -> bool:
        if not token:
            return False

        with self._token_lock:
            if token in self._validated_tokens:
                return self._validated_tokens[token]

        try:
            response = requests.get(
                "https://huggingface.co/api/whoami-v2",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            is_valid = response.status_code == 200
            with self._token_lock:
                self._validated_tokens[token] = is_valid
            return is_valid
        except Exception:
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # Strategia 1: HuggingFace Inference API (remote)
    # ──────────────────────────────────────────────────────────────────────────

    @retry(
        retry=tenacity.retry_if_exception_type(HfHubHTTPError),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(config.MAX_RETRIES),
        before_sleep=before_sleep_log(config.logger, logging.WARNING),
    )
    def _call_hf_api(
        self,
        client: InferenceClient,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Chiamata al modello tramite HuggingFace Inference API."""
        try:
            return client.text_generation(
                prompt,
                model=model,
                max_new_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            if "conversational" in str(e).lower() or "text-generation" in str(e).lower():
                response = client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response.choices[0].message.content or ""
            raise e

    # ──────────────────────────────────────────────────────────────────────────
    # Strategia 2: Server locale OpenAI-compatible (vLLM / Ollama / LM Studio)
    # ──────────────────────────────────────────────────────────────────────────

    @retry(
        retry=tenacity.retry_if_exception_type(openai.APIConnectionError),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(config.MAX_RETRIES),
        before_sleep=before_sleep_log(config.logger, logging.WARNING),
    )
    def _call_local_api(
        self,
        client: openai.OpenAI,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Chiamata al server locale tramite API OpenAI-compatible.
        Funziona con vLLM, Ollama (con --compat-openai), LM Studio, ecc.
        """
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    # ──────────────────────────────────────────────────────────────────────────
    # Strategia 3: Esecuzione Locale Nativa via Transformers
    # ──────────────────────────────────────────────────────────────────────────

    def _call_hf_local(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Esecuzione nativa in locale tramite HuggingFace transformers. Carica in memoria il modello alla prima richiesta."""
        import torch
        from transformers import pipeline
        
        # Inizializza o recupera la pipeline
        with self._pipeline_lock:
            if model not in self._local_pipelines:
                config.logger.info(f"Caricamento in corso del modello {model} in memoria (può richiedere svariati minuti)...")
                try:
                    # Usa device_map="auto" per sfruttare GPU se disponibile, e torch.float16 per ridurre RAM
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    dtype = torch.float16 if device == "cuda" else torch.float32
                    
                    pipe = pipeline(
                        "text-generation", 
                        model=model, 
                        torch_dtype=dtype,
                        device_map="auto" if device == "cuda" else None
                    )
                    self._local_pipelines[model] = pipe
                    config.logger.info(f"Modello {model} caricato con successo!")
                except Exception as e:
                    raise FatalWorkerError(f"Impossibile caricare il modello nativo {model}: {str(e)}")
            
            pipe = self._local_pipelines[model]

        # Inferenza
        try:
            # transformers dà errore se temp <= 0
            temp_val = max(0.01, temperature)
            result = pipe(
                prompt,
                max_new_tokens=max_tokens,
                temperature=temp_val,
                do_sample=True,
                return_full_text=False
            )
            return result[0]['generated_text'].strip()
        except Exception as e:
            raise FatalWorkerError(f"Errore inferenza nativa su {model}: {str(e)}")
