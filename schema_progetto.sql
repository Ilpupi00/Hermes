--
-- PostgreSQL database dump
--

-- Dumped from database version 16.2
-- Dumped by pg_dump version 16.4

-- Started on 2026-04-24 10:39:54

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 228 (class 1259 OID 49922)
-- Name: esecuzione; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.esecuzione (
    id_esecuzione integer NOT NULL,
    id_task integer,
    stato character varying(50),
    data_inizio timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    data_fine timestamp without time zone
);


ALTER TABLE public.esecuzione OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 49921)
-- Name: esecuzione_id_esecuzione_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.esecuzione_id_esecuzione_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.esecuzione_id_esecuzione_seq OWNER TO postgres;

--
-- TOC entry 4910 (class 0 OID 0)
-- Dependencies: 227
-- Name: esecuzione_id_esecuzione_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.esecuzione_id_esecuzione_seq OWNED BY public.esecuzione.id_esecuzione;


--
-- TOC entry 220 (class 1259 OID 49868)
-- Name: filecsv; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.filecsv (
    id_file integer NOT NULL,
    nome_file character varying(255) NOT NULL,
    numero_righe integer NOT NULL
);


ALTER TABLE public.filecsv OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 49867)
-- Name: filecsv_id_file_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.filecsv_id_file_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.filecsv_id_file_seq OWNER TO postgres;

--
-- TOC entry 4911 (class 0 OID 0)
-- Dependencies: 219
-- Name: filecsv_id_file_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.filecsv_id_file_seq OWNED BY public.filecsv.id_file;


--
-- TOC entry 224 (class 1259 OID 49896)
-- Name: mapping; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mapping (
    id_mapping integer NOT NULL,
    id_task integer,
    colonna_csv character varying(100) NOT NULL,
    placeholder_prompt character varying(100) NOT NULL
);


ALTER TABLE public.mapping OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 49895)
-- Name: mapping_id_mapping_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mapping_id_mapping_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.mapping_id_mapping_seq OWNER TO postgres;

--
-- TOC entry 4912 (class 0 OID 0)
-- Dependencies: 223
-- Name: mapping_id_mapping_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mapping_id_mapping_seq OWNED BY public.mapping.id_mapping;


--
-- TOC entry 218 (class 1259 OID 49859)
-- Name: modellillm; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.modellillm (
    id_modello integer NOT NULL,
    nome_modello character varying(100) NOT NULL,
    descrizione text
);


ALTER TABLE public.modellillm OWNER TO postgres;

--
-- TOC entry 217 (class 1259 OID 49858)
-- Name: modellillm_id_modello_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.modellillm_id_modello_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.modellillm_id_modello_seq OWNER TO postgres;

--
-- TOC entry 4913 (class 0 OID 0)
-- Dependencies: 217
-- Name: modellillm_id_modello_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.modellillm_id_modello_seq OWNED BY public.modellillm.id_modello;


--
-- TOC entry 226 (class 1259 OID 49908)
-- Name: righeinput; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.righeinput (
    id_riga_input integer NOT NULL,
    id_file integer,
    indice_riga integer NOT NULL,
    contenuto text NOT NULL
);


ALTER TABLE public.righeinput OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 49907)
-- Name: righeinput_id_riga_input_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.righeinput_id_riga_input_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.righeinput_id_riga_input_seq OWNER TO postgres;

--
-- TOC entry 4914 (class 0 OID 0)
-- Dependencies: 225
-- Name: righeinput_id_riga_input_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.righeinput_id_riga_input_seq OWNED BY public.righeinput.id_riga_input;


--
-- TOC entry 230 (class 1259 OID 49954)
-- Name: risultato; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.risultato (
    id_risultato integer NOT NULL,
    id_esecuzione integer,
    id_riga_input integer,
    id_file integer,
    output text,
    tempo_esecuzione double precision,
    stato character varying(50)
);


ALTER TABLE public.risultato OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 49953)
-- Name: risultato_id_risultato_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.risultato_id_risultato_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.risultato_id_risultato_seq OWNER TO postgres;

--
-- TOC entry 4915 (class 0 OID 0)
-- Dependencies: 229
-- Name: risultato_id_risultato_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.risultato_id_risultato_seq OWNED BY public.risultato.id_risultato;


--
-- TOC entry 222 (class 1259 OID 49875)
-- Name: task; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.task (
    id_task integer NOT NULL,
    id_utente integer,
    id_modello integer,
    nome character varying(100) NOT NULL,
    stato character varying(50) DEFAULT 'Bozza'::character varying,
    prompt text,
    dynamic_prompt text,
    data_creazione timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    temperatura double precision DEFAULT 0.1,
    max_tokens integer DEFAULT 500
);


ALTER TABLE public.task OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 49874)
-- Name: task_id_task_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.task_id_task_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.task_id_task_seq OWNER TO postgres;

--
-- TOC entry 4916 (class 0 OID 0)
-- Dependencies: 221
-- Name: task_id_task_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.task_id_task_seq OWNED BY public.task.id_task;


--
-- TOC entry 216 (class 1259 OID 49846)
-- Name: utenti; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.utenti (
    id_utente integer NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(100) NOT NULL,
    password character varying(255) NOT NULL,
    hub_token character varying(255)
);


ALTER TABLE public.utenti OWNER TO postgres;

--
-- TOC entry 215 (class 1259 OID 49845)
-- Name: utenti_id_utente_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.utenti_id_utente_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.utenti_id_utente_seq OWNER TO postgres;

--
-- TOC entry 4917 (class 0 OID 0)
-- Dependencies: 215
-- Name: utenti_id_utente_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.utenti_id_utente_seq OWNED BY public.utenti.id_utente;


--
-- TOC entry 4731 (class 2604 OID 49925)
-- Name: esecuzione id_esecuzione; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.esecuzione ALTER COLUMN id_esecuzione SET DEFAULT nextval('public.esecuzione_id_esecuzione_seq'::regclass);


--
-- TOC entry 4725 (class 2604 OID 49871)
-- Name: filecsv id_file; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.filecsv ALTER COLUMN id_file SET DEFAULT nextval('public.filecsv_id_file_seq'::regclass);


--
-- TOC entry 4729 (class 2604 OID 49899)
-- Name: mapping id_mapping; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mapping ALTER COLUMN id_mapping SET DEFAULT nextval('public.mapping_id_mapping_seq'::regclass);


--
-- TOC entry 4724 (class 2604 OID 49862)
-- Name: modellillm id_modello; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.modellillm ALTER COLUMN id_modello SET DEFAULT nextval('public.modellillm_id_modello_seq'::regclass);


--
-- TOC entry 4730 (class 2604 OID 49911)
-- Name: righeinput id_riga_input; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.righeinput ALTER COLUMN id_riga_input SET DEFAULT nextval('public.righeinput_id_riga_input_seq'::regclass);


--
-- TOC entry 4733 (class 2604 OID 49957)
-- Name: risultato id_risultato; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.risultato ALTER COLUMN id_risultato SET DEFAULT nextval('public.risultato_id_risultato_seq'::regclass);


--
-- TOC entry 4726 (class 2604 OID 49878)
-- Name: task id_task; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task ALTER COLUMN id_task SET DEFAULT nextval('public.task_id_task_seq'::regclass);


--
-- TOC entry 4723 (class 2604 OID 49849)
-- Name: utenti id_utente; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.utenti ALTER COLUMN id_utente SET DEFAULT nextval('public.utenti_id_utente_seq'::regclass);


--
-- TOC entry 4751 (class 2606 OID 49928)
-- Name: esecuzione esecuzione_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.esecuzione
    ADD CONSTRAINT esecuzione_pkey PRIMARY KEY (id_esecuzione);


--
-- TOC entry 4743 (class 2606 OID 49873)
-- Name: filecsv filecsv_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.filecsv
    ADD CONSTRAINT filecsv_pkey PRIMARY KEY (id_file);


--
-- TOC entry 4747 (class 2606 OID 49901)
-- Name: mapping mapping_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mapping
    ADD CONSTRAINT mapping_pkey PRIMARY KEY (id_mapping);


--
-- TOC entry 4741 (class 2606 OID 49866)
-- Name: modellillm modellillm_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.modellillm
    ADD CONSTRAINT modellillm_pkey PRIMARY KEY (id_modello);


--
-- TOC entry 4749 (class 2606 OID 49915)
-- Name: righeinput righeinput_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.righeinput
    ADD CONSTRAINT righeinput_pkey PRIMARY KEY (id_riga_input);


--
-- TOC entry 4753 (class 2606 OID 49961)
-- Name: risultato risultato_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.risultato
    ADD CONSTRAINT risultato_pkey PRIMARY KEY (id_risultato);


--
-- TOC entry 4745 (class 2606 OID 49884)
-- Name: task task_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task
    ADD CONSTRAINT task_pkey PRIMARY KEY (id_task);


--
-- TOC entry 4735 (class 2606 OID 49857)
-- Name: utenti utenti_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.utenti
    ADD CONSTRAINT utenti_email_key UNIQUE (email);


--
-- TOC entry 4737 (class 2606 OID 49853)
-- Name: utenti utenti_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.utenti
    ADD CONSTRAINT utenti_pkey PRIMARY KEY (id_utente);


--
-- TOC entry 4739 (class 2606 OID 49855)
-- Name: utenti utenti_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.utenti
    ADD CONSTRAINT utenti_username_key UNIQUE (username);


--
-- TOC entry 4758 (class 2606 OID 49929)
-- Name: esecuzione esecuzione_id_task_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.esecuzione
    ADD CONSTRAINT esecuzione_id_task_fkey FOREIGN KEY (id_task) REFERENCES public.task(id_task);


--
-- TOC entry 4756 (class 2606 OID 49902)
-- Name: mapping mapping_id_task_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mapping
    ADD CONSTRAINT mapping_id_task_fkey FOREIGN KEY (id_task) REFERENCES public.task(id_task) ON DELETE CASCADE;


--
-- TOC entry 4757 (class 2606 OID 49916)
-- Name: righeinput righeinput_id_file_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.righeinput
    ADD CONSTRAINT righeinput_id_file_fkey FOREIGN KEY (id_file) REFERENCES public.filecsv(id_file) ON DELETE CASCADE;


--
-- TOC entry 4759 (class 2606 OID 49962)
-- Name: risultato risultato_id_esecuzione_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.risultato
    ADD CONSTRAINT risultato_id_esecuzione_fkey FOREIGN KEY (id_esecuzione) REFERENCES public.esecuzione(id_esecuzione) ON DELETE CASCADE;


--
-- TOC entry 4760 (class 2606 OID 49972)
-- Name: risultato risultato_id_file_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.risultato
    ADD CONSTRAINT risultato_id_file_fkey FOREIGN KEY (id_file) REFERENCES public.filecsv(id_file) ON DELETE CASCADE;


--
-- TOC entry 4761 (class 2606 OID 49967)
-- Name: risultato risultato_id_riga_input_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.risultato
    ADD CONSTRAINT risultato_id_riga_input_fkey FOREIGN KEY (id_riga_input) REFERENCES public.righeinput(id_riga_input) ON DELETE CASCADE;


--
-- TOC entry 4754 (class 2606 OID 49890)
-- Name: task task_id_modello_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task
    ADD CONSTRAINT task_id_modello_fkey FOREIGN KEY (id_modello) REFERENCES public.modellillm(id_modello);


--
-- TOC entry 4755 (class 2606 OID 49885)
-- Name: task task_id_utente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task
    ADD CONSTRAINT task_id_utente_fkey FOREIGN KEY (id_utente) REFERENCES public.utenti(id_utente);


-- Completed on 2026-04-24 10:39:54

--
-- PostgreSQL database dump complete
--

--
-- TOC entry (Amministratori)
--
CREATE TABLE public.amministratori (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    hashed_password character varying(255) NOT NULL
);

ALTER TABLE public.amministratori OWNER TO postgres;

CREATE SEQUENCE public.amministratori_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.amministratori_id_seq OWNER TO postgres;
ALTER SEQUENCE public.amministratori_id_seq OWNED BY public.amministratori.id;
ALTER TABLE ONLY public.amministratori ALTER COLUMN id SET DEFAULT nextval('public.amministratori_id_seq'::regclass);

ALTER TABLE ONLY public.amministratori
    ADD CONSTRAINT amministratori_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.amministratori
    ADD CONSTRAINT amministratori_username_key UNIQUE (username);


