from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey

from .db import Base

class Utente(Base):
    __tablename__ = "utenti"
    id_utente = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, default="default")
    email = Column(String(100), nullable=False, default="default@hermes.local")
    password = Column(String(255), nullable=False, default="default")
    hub_token = Column(String(255))

class ModelloLLM(Base):
    __tablename__ = "modellillm"
    id_modello    = Column(Integer, primary_key=True, index=True)
    nome_modello  = Column(String(100), nullable=False)
    # 'hf_api'    → HuggingFace Inference API (remote, usa hub_token + nome_modello)
    # 'local_url' → Server OpenAI-compatible locale (vLLM, Ollama, LM Studio…)
    tipo          = Column(String(20), nullable=False, default="hf_api")
    # URL base del server locale (es. http://localhost:11434/v1) — solo per local_url
    endpoint_url  = Column(String(500), nullable=True)
    descrizione   = Column(Text, nullable=True)

class Task(Base):
    __tablename__ = "task"
    id_task = Column(Integer, primary_key=True, index=True)
    id_utente = Column(Integer, ForeignKey("utenti.id_utente"))
    id_modello = Column(Integer, ForeignKey("modellillm.id_modello"))
    nome = Column(String(100), nullable=False)
    stato = Column(String(50), default="Bozza")
    prompt = Column(Text)
    dynamic_prompt = Column(Text)
    temperatura = Column(Float, default=0.1)
    max_tokens = Column(Integer, default=500)

class Esecuzione(Base):
    __tablename__ = "esecuzione"
    id_esecuzione = Column(Integer, primary_key=True, index=True)
    id_task = Column(Integer, ForeignKey("task.id_task"))
    totale_righe = Column(Integer, default=0)

class Risultato(Base):
    __tablename__ = "risultato"
    id_risultato = Column(Integer, primary_key=True, index=True)
    id_esecuzione = Column(Integer, ForeignKey("esecuzione.id_esecuzione"))
    id_riga_input = Column(Integer) # ForeignKey in teoria, ma a noi basta l'ID
    id_file = Column(Integer)
    output = Column(Text)
    tempo_esecuzione = Column(Float)
    stato = Column(String(50))