from .dashboard import router as dashboard_router
from .control import router as control_router
from .logs import router as logs_router
from .models import router as models_router
from .upload import router as upload_router
from .auth import router as auth_router

__all__ = ["dashboard_router", "control_router", "logs_router", "models_router", "upload_router", "auth_router"]
