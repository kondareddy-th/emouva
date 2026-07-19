"""Conversational Portfolio Advisor — multi-turn chat with SSE streaming."""

import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_api_key, get_claude_model, rate_limit, get_optional_user
from app.models.db import AdvisorSession
from app.services import claude
from app.services import robinhood_store as store, robinhood_portfolio as rp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/advisor", tags=["advisor"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
}


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class AdvisorChatRequest(BaseModel):
    messages: list[ChatMessage]
    portfolio_context: str | None = None
    document_context: str | None = None
    account: str | None = None  # which Robinhood account's portfolio to use


@router.post("/chat")
async def advisor_chat(
    req: AdvisorChatRequest,
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    user=Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    _rate: None = Depends(rate_limit("advisor")),
):
    """SSE endpoint for multi-turn portfolio advisor chat.
    Events: status (progress), context (portfolio data), delta (AI tokens), done (final text), error.
    """
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    # Resolve the per-user MCP token for the requested account (only needed on the
    # first turn, when portfolio_context isn't cached client-side yet).
    token = None
    if user and not req.portfolio_context:
        token = await store.get_valid_access_token(db, user.id)

    async def event_generator():
        async for event in claude.stream_advisor_chat(
            messages=messages,
            api_key=api_key,
            portfolio_context=req.portfolio_context,
            document_context=req.document_context,
            model=claude_model,
            token=token,
            account=req.account,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Session history ─────────────────────────────────────────────

class SaveSessionRequest(BaseModel):
    messages: list[dict] = []
    title: str | None = None
    account: str | None = None


def _derive_title(messages: list[dict]) -> str:
    for m in messages or []:
        if m.get("role") == "user" and m.get("content"):
            t = " ".join(str(m["content"]).split())
            return (t[:60] + "…") if len(t) > 60 else t
    return "New chat"


async def _load_session(db: AsyncSession, user_id, session_id: str):
    import uuid
    try:
        sid = uuid.UUID(session_id)
    except (ValueError, AttributeError, TypeError):
        return None
    return (await db.execute(
        select(AdvisorSession).where(AdvisorSession.id == sid, AdvisorSession.user_id == user_id)
    )).scalar_one_or_none()


@router.get("/sessions")
async def list_sessions(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Recent Advisor sessions for the current user (most recent first)."""
    if not user:
        return {"sessions": []}
    rows = (await db.execute(
        select(AdvisorSession).where(AdvisorSession.user_id == user.id)
        .order_by(AdvisorSession.updated_at.desc()).limit(50)
    )).scalars().all()
    return {"sessions": [{
        "id": str(s.id), "title": s.title, "account": s.account,
        "message_count": len(s.messages or []),
        "updated_at": s.updated_at.isoformat(),
    } for s in rows]}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user=Depends(get_optional_user),
                      db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    s = await _load_session(db, user.id, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return {"id": str(s.id), "title": s.title, "account": s.account, "messages": s.messages or []}


@router.post("/sessions")
async def create_session(payload: SaveSessionRequest = Body(default_factory=SaveSessionRequest),
                         user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    s = AdvisorSession(
        user_id=user.id, account=payload.account,
        title=payload.title or _derive_title(payload.messages),
        messages=payload.messages or [],
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": str(s.id), "title": s.title, "account": s.account}


@router.put("/sessions/{session_id}")
async def save_session(session_id: str, payload: SaveSessionRequest,
                       user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    s = await _load_session(db, user.id, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    s.messages = payload.messages
    if payload.account is not None:
        s.account = payload.account
    if not s.title or s.title == "New chat":
        s.title = payload.title or _derive_title(payload.messages)
    await db.commit()
    return {"ok": True, "title": s.title}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user=Depends(get_optional_user),
                         db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    s = await _load_session(db, user.id, session_id)
    if s:
        await db.delete(s)
        await db.commit()
    return {"ok": True}


@router.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document (PDF or text) and extract its text content.

    Returns the extracted text immediately so the frontend can include it
    in subsequent chat messages as document_context.
    """
    if not file.content_type:
        raise HTTPException(400, "File type not detected")

    # Allow common PDF mime types
    content_type = file.content_type.lower()
    is_pdf = content_type in ("application/pdf", "application/x-pdf")
    is_text = content_type.startswith("text/")

    if not is_pdf and not is_text:
        raise HTTPException(
            400,
            f"Unsupported file type: {file.content_type}. Upload PDF or text files.",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Max size is {MAX_FILE_SIZE // (1024*1024)} MB.")

    filename = file.filename or "document"

    if is_pdf:
        try:
            import pdfplumber

            text_parts: list[str] = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

            if not text_parts:
                raise HTTPException(400, "Could not extract text from PDF. It may be image-only.")

            extracted = "\n\n".join(text_parts)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("PDF parsing failed for %s", filename)
            raise HTTPException(400, f"Failed to parse PDF: {e}")
    else:
        # Plain text / markdown / csv
        try:
            extracted = content.decode("utf-8")
        except UnicodeDecodeError:
            extracted = content.decode("latin-1")

    # Truncate very long documents to ~100k chars (~25k tokens)
    max_chars = 100_000
    truncated = len(extracted) > max_chars
    if truncated:
        extracted = extracted[:max_chars] + "\n\n[Document truncated — first 100,000 characters shown]"

    logger.info(
        "Document parsed: %s (%d bytes -> %d chars text, truncated=%s)",
        filename, len(content), len(extracted), truncated,
    )

    return {
        "filename": filename,
        "text": extracted,
        "char_count": len(extracted),
        "truncated": truncated,
    }
