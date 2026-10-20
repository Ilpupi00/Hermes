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
import openai

from ..core import config
from ..core.prompt_template import PromptTemplateError, render_prompt
from ..db.db import SessionLocal
from ..db import repository
from ..db.status import ResultStatus
from .worker_base import WorkerBase, FatalWorkerError


def _is_retryable_hf_error(error: BaseException) -> bool:
    """Ritenta solo errori HF plausibilmente transitori."""
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        return status_code in {408, 429} or status_code >= 500

    error_name = type(error).__name__.lower()
    return "timeout" in error_name or "connection" in error_name


def _raise_for_fatal_hf_error(error: Exception, model: str) -> None:
    """Traduce gli errori HF permanenti in errori fatali e azionabili."""
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    message = str(error).lower()

    if (
        status_code == 402
        or "402 payment required" in message
        or "no remaining credits" in message
    ):
        raise FatalWorkerError(
            "Credito Hugging Face esaurito. Acquista crediti prepagati o "
            "configura una modalità di fatturazione valida prima di "
            "riavviare il job."
        ) from error

    if (
        "model_not_supported" in message
        or "not supported by any provider" in message
    ):
        raise FatalWorkerError(
            f"Il modello '{model}' non è disponibile tramite i provider "
            "Hugging Face abilitati per questo account. Abilita un provider "
            "compatibile nelle impostazioni Inference Providers oppure "
            "seleziona un altro modello."
        ) from error


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
            prompt_mapping = context.get("prompt_mapping", {})
            temperatura  = context["temperatura"]
            max_tokens   = context["max_tokens"]
            context_file = context["id_file"]

            if context_file is None or int(context_file) != id_file:
                raise FatalWorkerError(
                    f"File {id_file} non associato all'esecuzione {id_esecuzione}."
                )

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
                client = InferenceClient(
                    provider=config.HF_INFERENCE_PROVIDER,
                    api_key=token,
                )
                call_fn = lambda prompt: self._call_hf_api(
                    client, modello, prompt, temperatura, max_tokens
                )
                config.logger.info(
                    f"[AI] client=HuggingFaceAPI provider="
                    f"{config.HF_INFERENCE_PROVIDER} modello={modello} pronto"
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

            row_indexes = [int(index) for index in chunk.index]
            try:
                input_row_ids = repository.get_input_row_ids(
                    db, id_file, row_indexes
                )
            except Exception as e:
                raise FatalWorkerError(f"Errore righe input: {str(e)}")

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

                    id_riga = input_row_ids[int(index)]
                    dati_riga = row.drop("id_riga_input", errors='ignore').to_dict()
                    try:
                        rendered_prompt = render_prompt(
                            prompt_base,
                            dati_riga,
                            prompt_mapping,
                        )
                    except PromptTemplateError as error:
                        raise FatalWorkerError(
                            f"Prompt parametrico non applicabile: {error}"
                        ) from error

                    prompt_ok = (
                        rendered_prompt
                        if prompt_mapping
                        else f"{rendered_prompt}\n\nDati:\n{dati_riga}"
                    )

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
                            risposta, tempo, ResultStatus.COMPLETED.value
                        )
                        db.commit()
                        completate += 1
                        config.logger.info(
                            f"[AI] chunk={chunk_index} riga={id_riga} "
                            f"status=OK tempo={tempo}s tokens_out={len(risposta.split())}"
                        )
                    except FatalWorkerError:
                        db.rollback()
                        raise
                    except Exception as e:
                        errori += 1
                        config.logger.error(
                            f"[AI] chunk={chunk_index} riga={id_riga} "
                            f"status=ERROR reason={str(e)[:120]}"
                        )
                        repository.save_result(
                            db,
                            id_esecuzione,
                            id_file,
                            id_riga,
                            str(e),
                            0.0,
                            ResultStatus.ERROR.value,
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

        return {
            "status": "ok" if errori == 0 else "error",
            "completed_rows": completate,
            "error_rows": errori,
            **metadata,
        }

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
        retry=tenacity.retry_if_exception(_is_retryable_hf_error),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(config.MAX_RETRIES),
        before_sleep=before_sleep_log(config.logger, logging.WARNING),
        reraise=True,
    )
    def _call_hf_api(
        self,
        client: InferenceClient,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Chiama un modello Instruct remoto tramite Hugging Face Chat Completion."""
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            _raise_for_fatal_hf_error(e, model)
            raise

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
