"""Per-account memory — continuity for the agent across ticks (ARCHITECTURE: the
'continuous, human-like context' layer).

Two tiers:
  • short-term — one compact, DETERMINISTIC summary per day (built from the ledger),
    kept for the current week.
  • long-term  — a curated knowledge doc (holdings history, lessons, per-name
    knowledge, standing context), rewritten weekly by an LLM 'librarian'.

Every tick reads build_block() so the brain remembers what it did and learned. The
weekly compaction (compact_weekly) folds the week's daily logs into long-term and
keeps it size-budgeted, so per-tick context stays flat no matter how long it runs.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, distinct

from app.database import async_session
from app.models.db import AgentLedgerEntry, AgentMemory, AgentMemoryDay

logger = logging.getLogger(__name__)

# ledger types that matter for memory (routine holds are counted, not listed)
_NOTABLE = {"executed", "veto", "awaiting", "declined", "note", "error"}
_WITH_BODY = {"veto", "note", "error"}          # for these, keep a bit of the reason
LONG_TERM_BUDGET = 2000                         # chars — long-term stays compact


def _utcnow() -> datetime:
    return datetime.utcnow()


def _day_start(d) -> datetime:
    return datetime(d.year, d.month, d.day)


def _summarize(entries) -> str:
    """Deterministic compact summary of a set of ledger entries."""
    parts = []
    for e in entries:
        if e.type not in _NOTABLE:
            continue
        line = (e.meta or {}).get("order_line") or e.title or e.type
        if e.body and e.type in _WITH_BODY:
            line += f" — {e.body[:80]}"
        parts.append(line)
    holds = sum(1 for e in entries if e.type == "check")
    if holds:
        parts.append(f"held {holds}×")
    return "; ".join(parts) if parts else "quiet — no actions"


async def build_block(db, account: str) -> str:
    """The memory block fed to the brain each tick: long-term knowledge + this
    week's daily logs + today's live activity + the most recent double-check veto."""
    today = _utcnow().date()
    week_start = today - timedelta(days=7)

    mem = (await db.execute(select(AgentMemory).where(AgentMemory.account == account))).scalar_one_or_none()
    days = (await db.execute(select(AgentMemoryDay).where(
        AgentMemoryDay.account == account, AgentMemoryDay.day >= week_start
    ).order_by(AgentMemoryDay.day))).scalars().all()
    today_entries = (await db.execute(select(AgentLedgerEntry).where(
        AgentLedgerEntry.account == account, AgentLedgerEntry.ts >= _day_start(today)
    ).order_by(AgentLedgerEntry.ts))).scalars().all()

    out = []
    if mem and mem.long_term:
        out.append("ACCOUNT MEMORY (long-term — durable knowledge & lessons):\n" + mem.long_term.strip())
    if days:
        out.append("THIS WEEK:\n" + "\n".join(f"  {d.day:%b %d}: {d.summary}" for d in days))
    if today_entries:
        out.append(f"TODAY ({today:%b %d}):\n  " + _summarize(today_entries))
    veto = next((e for e in reversed(today_entries) if e.type == "veto"), None)
    if veto:
        out.append("LAST DOUBLE-CHECK VETO: " + (veto.title or "")
                   + (f" — {veto.body[:140]}" if veto.body else "")
                   + "\nWeigh this before re-proposing the same buy.")
    return "\n\n".join(out) if out else "No prior activity on this account yet — a fresh start."


async def record_daily(db=None) -> dict:
    """End-of-day (deterministic, no LLM): fold each account's notable ledger events
    into one compact daily-log row (short-term memory)."""
    own = db is None
    db = db or async_session()
    try:
        today = _utcnow().date()
        start = _day_start(today)
        accounts = (await db.execute(select(distinct(AgentLedgerEntry.account))
                                     .where(AgentLedgerEntry.ts >= start))).scalars().all()
        n = 0
        for acct in accounts:
            entries = (await db.execute(select(AgentLedgerEntry).where(
                AgentLedgerEntry.account == acct, AgentLedgerEntry.ts >= start
            ).order_by(AgentLedgerEntry.ts))).scalars().all()
            summary = _summarize(entries)
            uid = entries[0].user_id if entries else None
            row = (await db.execute(select(AgentMemoryDay).where(
                AgentMemoryDay.account == acct, AgentMemoryDay.day == today))).scalar_one_or_none()
            if row:
                row.summary = summary
            else:
                db.add(AgentMemoryDay(account=acct, user_id=uid, day=today, summary=summary))
            n += 1
        await db.commit()
        logger.info("Daily memory: wrote %d account daily-log(s)", n)
        return {"accounts": n}
    finally:
        if own:
            await db.close()


_MEMORY_TOOL = {
    "name": "memory_update",
    "description": "The rewritten, compact long-term account memory.",
    "input_schema": {
        "type": "object",
        "properties": {"long_term": {"type": "string",
                       "description": "the FULL updated memory doc — compact markdown, durable knowledge + lessons only"}},
        "required": ["long_term"],
    },
}


async def compact_weekly(db=None) -> dict:
    """Weekly 'librarian' (LLM): fold this week's daily logs into the long-term memory
    — keep durable knowledge + lessons, prune stale detail, stay under the size
    budget — then clear the folded daily logs. Runs Sunday."""
    own = db is None
    db = db or async_session()
    try:
        from app.services.agent import research
        accounts = (await db.execute(select(distinct(AgentMemoryDay.account)))).scalars().all()
        updated = 0
        for acct in accounts:
            days = (await db.execute(select(AgentMemoryDay).where(
                AgentMemoryDay.account == acct).order_by(AgentMemoryDay.day))).scalars().all()
            if not days:
                continue
            mem = (await db.execute(select(AgentMemory).where(AgentMemory.account == acct))).scalar_one_or_none()
            existing = (mem.long_term if mem and mem.long_term else "").strip() or "(empty — first consolidation)"
            logs = "\n".join(f"{d.day:%b %d}: {d.summary}" for d in days)
            system = (
                "You are the memory librarian for a patient, Munger-style value-investing agent. Maintain a "
                f"COMPACT durable memory for ONE account, UNDER {LONG_TERM_BUDGET} characters. Merge this week's "
                "daily logs into the existing memory. Keep these sections: Holdings (what we own/owned + entry + "
                "thesis + conviction), Lessons (what worked/failed — turn repeated double-check VETOES and mistakes "
                "into durable lessons), Knowledge (durable per-name facts learned), Context (account size, circle, "
                "margin bar, risk posture). Prune stale one-off detail; preserve knowledge and lessons. Be terse. "
                "Return the FULL updated memory via memory_update.")
            user = (f"EXISTING LONG-TERM MEMORY:\n{existing}\n\nTHIS WEEK'S DAILY LOGS:\n{logs}\n\n"
                    f"Rewrite the long-term memory (≤{LONG_TERM_BUDGET} chars).")
            out = await asyncio.to_thread(research._llm_json, system, user, _MEMORY_TOOL, 1500)
            if not out or not out.get("long_term"):
                continue
            new_lt = out["long_term"].strip()[: LONG_TERM_BUDGET * 2]   # hard safety cap
            if mem:
                mem.long_term = new_lt
            else:
                db.add(AgentMemory(account=acct, user_id=days[0].user_id, long_term=new_lt))
            for d in days:                          # the week is now folded into long-term
                await db.delete(d)
            updated += 1
            await db.commit()                       # per-account so a failure mid-run doesn't lose progress
        logger.info("Weekly memory compaction: %d account(s) consolidated", updated)
        return {"consolidated": updated}
    finally:
        if own:
            await db.close()
