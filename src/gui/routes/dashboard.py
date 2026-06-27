import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/")
async def get_dashboard():
    """Serve la pagina HTML principale."""
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pages", "index.html"))
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
