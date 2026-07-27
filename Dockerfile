# Usiamo la versione di Python 3.12 stabile e leggera
FROM python:3.12-slim

# Evita la creazione di file .pyc e forza l'output immediato dei log
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Imposta la directory di lavoro dentro il container
WORKDIR /app

# Installa 'uv' per una gestione rapidissima delle dipendenze
RUN pip install --no-cache-dir uv

# Il runtime Docker usa API remote o server OpenAI-compatible. Le dipendenze
# native Transformers/PyTorch restano opzionali sul sistema host: su Apple
# Silicon una build Linux scaricherebbe inutilmente librerie CUDA.
COPY requirements-runtime.txt .
RUN uv pip install --system -r requirements-runtime.txt

# Copia tutto il codice sorgente
COPY src/ ./src/
COPY scripts/ ./scripts/

# Crea le cartelle di base per i CSV
RUN mkdir -p /app/uploads_web /app/processed /app/failed /app/interrupted

# Esponiamo la porta 8000 per la Dashboard Web
EXPOSE 8000

# Avvia l'applicazione direttamente tramite Uvicorn (Server Mode, niente finestra Desktop)
CMD ["uvicorn", "src.gui.app:app", "--host", "0.0.0.0", "--port", "8000"]
