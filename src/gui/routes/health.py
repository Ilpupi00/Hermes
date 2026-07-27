from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...core.config import logger
from ...db.db import engine

router = APIRouter()


@router.get("/health", include_in_schema=False)
def health():
    """Report application readiness, including the PostgreSQL connection."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error("status=health_check_failed database=unavailable error=%s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "unavailable"},
        )

    return {"status": "ok", "database": "ok"}
