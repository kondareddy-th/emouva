


from fastapi import APIRouter

from app.config import settings
from app.services import robinhood

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "model": settings.claude_model,
        "robinhood_connected": robinhood.is_connected(),
    }
