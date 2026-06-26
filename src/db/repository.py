from sqlalchemy.orm import Session
from .models import Esecuzione, Task, Utente, ModelloLLM, Risultato

def get_execution_context(db: Session, id_esecuzione: int) -> dict:
    result = (
        db.query(
            Utente.hub_token, 
            Task.prompt, 
            ModelloLLM.nome_modello,
            Task.temperatura,
            Task.max_tokens
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
        "hub_token": result.hub_token,
        "prompt": result.prompt,
        "nome_modello": result.nome_modello,
        "temperatura": result.temperatura if result.temperatura is not None else 0.1,
        "max_tokens": result.max_tokens if result.max_tokens is not None else 500
    }

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