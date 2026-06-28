from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import URL
# Import corretto: DB_PASSWORD
from ..core.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

SQLALCHEMY_DATABASE_URL = URL.create(
    "postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT) if DB_PORT else None,
    database=DB_NAME,
)

# pool_size=10, max_overflow=20 è perfetto per il nostro ThreadPoolExecutor
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_size=10, max_overflow=20)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()