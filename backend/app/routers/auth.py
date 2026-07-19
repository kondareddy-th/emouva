"""
Authentication & brokerage connection endpoints.
Users connect their brokerage from Settings → Connections.
"""

import logging
from threading import Thread

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_optional_user
from app.services import robinhood
from app.services import robinhood_store as store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class ConnectRequest(BaseModel):
    username: str
    password: str
    mfa_code: str | None = None


class ConnectionStatus(BaseModel):
    connected: bool
    source: str  # "robinhood" | "disconnected"


class ConnectResponse(BaseModel):
    status: str  # "connected" | "connecting" | "failed"
    message: str = ""


@router.get("/status", response_model=ConnectionStatus)
async def connection_status(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Connected if the user has an OAuth Robinhood (agentic MCP) connection."""
    connected = False
    if user:
        conn = await store.get_connection(db, user.id)
        connected = conn is not None
    if not connected:
        connected = robinhood.is_connected()  # legacy fallback
    return ConnectionStatus(
        connected=connected,
        source="robinhood" if connected else "disconnected",
    )


@router.post("/connect", response_model=ConnectResponse)
def connect_robinhood(req: ConnectRequest):
    """
    Initiate Robinhood connection.
    The login may trigger device verification — user must approve
    on their Robinhood app. This call blocks until verified or timeout.
    """
    result = robinhood.login(
        username=req.username,
        password=req.password,
        mfa_code=req.mfa_code,
    )
    return ConnectResponse(
        status=result["status"],
        message=result.get("message", ""),
    )


@router.post("/disconnect")
def disconnect_robinhood():
    """Disconnect from Robinhood and clear saved session."""
    robinhood.logout()
    return {"status": "disconnected"}
