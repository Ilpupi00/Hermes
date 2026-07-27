from sqlalchemy import Column, DateTime, Integer, String, Text, Float, ForeignKey
from sqlalchemy.sql import func

from .db import Base

class Utente(Base):
    __tablename__ = "utenti"
    id_utente = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    hub_token = Column(String(255))

class Admin(Base):
    __tablename__ = "amministratori"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

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
    data_creazione = Column(DateTime, server_default=func.now())

class FileCSV(Base):
    __tablename__ = "filecsv"
    id_file = Column(Integer, primary_key=True, index=True)
    nome_file = Column(String(255), nullable=False)
    numero_righe = Column(Integer, nullable=False)

class Mapping(Base):
    __tablename__ = "mapping"
    id_mapping = Column(Integer, primary_key=True, index=True)
    id_task = Column(Integer, ForeignKey("task.id_task", ondelete="CASCADE"))
    colonna_csv = Column(String(100), nullable=False)
    placeholder_prompt = Column(String(100), nullable=False)

class RigaInput(Base):
    __tablename__ = "righeinput"
    id_riga_input = Column(Integer, primary_key=True, index=True)
    id_file = Column(Integer, ForeignKey("filecsv.id_file", ondelete="CASCADE"))
    indice_riga = Column(Integer, nullable=False)
    contenuto = Column(Text, nullable=False)

class Esecuzione(Base):
    __tablename__ = "esecuzione"
    id_esecuzione = Column(Integer, primary_key=True, index=True)
    id_task = Column(Integer, ForeignKey("task.id_task"))
    stato = Column(String(50))
    data_inizio = Column(DateTime, server_default=func.now())
    data_fine = Column(DateTime)
    totale_righe = Column(Integer, nullable=False, default=0)

class Risultato(Base):
    __tablename__ = "risultato"
    id_risultato = Column(Integer, primary_key=True, index=True)
    id_esecuzione = Column(Integer, ForeignKey("esecuzione.id_esecuzione"))
    id_riga_input = Column(Integer, ForeignKey("righeinput.id_riga_input", ondelete="CASCADE"))
    id_file = Column(Integer, ForeignKey("filecsv.id_file", ondelete="CASCADE"))
    output = Column(Text)
    tempo_esecuzione = Column(Float)
    stato = Column(String(50))
