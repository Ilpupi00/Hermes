-- Migration: Hermes Hybrid AI — Estensione tabella modellillm
-- Aggiunge le colonne tipo, endpoint_url, descrizione in modo additivo (non distruttivo).
-- Può essere rieseguito senza errori grazie a IF NOT EXISTS.
-- Eseguire sul DB PostgreSQL con: psql -U postgres -d <db> -f 001_modellillm_hybrid.sql

ALTER TABLE public.modellollm
    ADD COLUMN IF NOT EXISTS tipo         VARCHAR(20) NOT NULL DEFAULT 'hf_api',
    ADD COLUMN IF NOT EXISTS endpoint_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS descrizione  TEXT;

-- Commento descrittivo per documentazione
COMMENT ON COLUMN public.modellollm.tipo IS
    'Modalità di inferenza: hf_api (HuggingFace remote), local_url (server OpenAI-compatible locale), oppure hf_local (esecuzione nativa via Transformers)';
COMMENT ON COLUMN public.modellollm.endpoint_url IS
    'URL base del server locale OpenAI-compatible (es. http://localhost:11434/v1). Usato solo quando tipo=local_url';
COMMENT ON COLUMN public.modellollm.descrizione IS
    'Descrizione libera del modello';
