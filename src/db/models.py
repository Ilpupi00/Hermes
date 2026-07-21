from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey
from .db import Base

class Utente(Base):
    __tablename__ = "utenti"
    id_utente = Column(Integer, primary_key=True, index=True)
    hub_token = Column(String(255))

class ModelloLLM(Base):
    __tablename__ = "modellillm"
    id_modello = Column(Integer, primary_key=True, index=True)
    nome_modello = Column(String(100), nullable=False)

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

class Risultato(Base):
    __tablename__ = "risultato"
    id_risultato = Column(Integer, primary_key=True, index=True)
    id_esecuzione = Column(Integer, ForeignKey("esecuzione.id_esecuzione"))
    id_riga_input = Column(Integer) # ForeignKey in teoria, ma a noi basta l'ID
    id_file = Column(Integer)
    output = Column(Text)
    tempo_esecuzione = Column(Float)
    stato = Column(String(50))

class Admin(Base):
    __tablename__ = "amministratori"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)