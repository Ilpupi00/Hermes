import pandas as pd
import time
import requests
import tenacity
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
import logging
import threading
from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError

from ..core import config
from ..core.prompt_template import PromptTemplateError, render_prompt
from ..db.db import SessionLocal
from ..db import repository
from ..db.status import ResultStatus
from .worker_base import WorkerBase, FatalWorkerError

class LocalAIWorker(WorkerBase):
    _validated_tokens = {}
    _token_lock = threading.Lock()
    
    def process(self, chunk: pd.DataFrame, metadata: dict) -> dict:
        filename = metadata.get("filename")
        
        try:
            parts = filename.split('_')
            id_esecuzione = int(parts[1])
            id_file = int(parts[3].split('.')[0])
        except Exception:
            raise FatalWorkerError(f"Nome file non valido: {filename}")

        with SessionLocal() as db:
            try:
                context = repository.get_execution_context(db, id_esecuzione)
            except Exception as e:
                raise FatalWorkerError(f"Errore DB: {str(e)}")

            token = context['hub_token']
            modello = context['nome_modello']
            prompt_base = context['prompt']
            prompt_mapping = context.get('prompt_mapping', {})
            
            # --- PARAMETRI DINAMICI DAL DATABASE ---
            temp_db = context['temperatura']
            max_tok_db = context['max_tokens']

            # Validazione Token su Hugging Face
            if not self._is_token_valid(token):
                raise FatalWorkerError("Token non valido o revocato.")

            # Inizializza client Hugging Face
            client = InferenceClient(
                provider=config.HF_INFERENCE_PROVIDER,
                api_key=token,
            )
            
            try:
                for index, row in chunk.iterrows():
                    # Cancellazione cooperativa
                    cancel_event = metadata.get("cancel_event")
                    if cancel_event and cancel_event.is_set():
                        config.logger.warning(f"Process interrotto per il chunk {metadata.get('chunk_index')}")
                        raise FatalWorkerError("Elaborazione interrotta per attivazione Circuit Breaker.")

                    id_riga = row['id_riga_input']
                    dati_riga = row.drop('id_riga_input').to_dict()
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

                    prompt_finale = (
                        rendered_prompt
                        if prompt_mapping
                        else f"{rendered_prompt}\n\nDati:\n{dati_riga}"
                    )
                    
                    start_time = time.time()
                    try:
                        # Passiamo temp_db e max_tok_db presi dal database!
                        risposta = self._call_ai(client, modello, prompt_finale, temp_db, max_tok_db)
                        tempo = round(time.time() - start_time, 2)
                        repository.save_result(
                            db,
                            id_esecuzione,
                            id_file,
                            id_riga,
                            risposta,
                            tempo,
                            ResultStatus.COMPLETED.value,
                        )
                    except Exception as e:
                        config.logger.error(f"Riga {id_riga} fallita: {str(e)}")
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
            except Exception as db_err:
                db.rollback()
                if isinstance(db_err, FatalWorkerError):
                    raise
                config.logger.error(f"Errore durante commit del chunk: {str(db_err)}")
                raise FatalWorkerError(f"Impossibile salvare i risultati del chunk: {str(db_err)}")

        return {"status": "ok", **metadata}

    def _is_token_valid(self, token: str) -> bool:
        if not token:
            return False
            
        with self._token_lock:
            if token in self._validated_tokens:
                return self._validated_tokens[token]
                
        try:
            # Controllo reale su API Hugging Face
            response = requests.get(
                "https://huggingface.co/api/whoami-v2", 
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            is_valid = response.status_code == 200
            with self._token_lock:
                self._validated_tokens[token] = is_valid
            return is_valid
        except Exception:
            return False

    @retry(
        retry=tenacity.retry_if_exception_type(HfHubHTTPError),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(config.MAX_RETRIES),
        before_sleep=before_sleep_log(config.logger, logging.WARNING)
    )
    def _call_ai(self, client: InferenceClient, model: str, prompt: str, temperature: float, max_tokens: int) -> str:
        """Chiama il modello tramite Hugging Face usando parametri interamente dinamici."""
        response = client.text_generation(
            prompt,
            model=model,
            max_new_tokens=max_tokens,      # <-- Ora è dinamico
            temperature=temperature         # <-- Ora è dinamico
        )
        return response
