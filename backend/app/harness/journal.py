"""Decision journal — append-only audit trail of every tick.

File-backed (JSONL per user) for the slice; swap for a Postgres table in
production (same `append` / `tail` surface). Powers the activity feed and the
just-in-time "what did I do last time and why" recall in the next tick.
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import JOURNAL_ROOT
from .state import Decision


class Journal:
    def __init__(self, user_id: str, root: Path | None = None):
        self.user_id = user_id
        self.path = (root or JOURNAL_ROOT) / f"{user_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, decision: Decision) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(decision.model_dump_json() + "\n")

    def tail(self, n: int = 5) -> list[Decision]:
        if not self.path.is_file():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-n:]
        return [Decision.model_validate_json(ln) for ln in lines]

    def tail_summary(self, n: int = 5) -> str:
        """Compact, model-friendly recap of recent decisions for the next tick."""
        out = []
        for d in self.tail(n):
            p = d.proposal
            verb = p.action.value.upper()
            tgt = f"{p.qty:g} {p.symbol}" if p.symbol else ""
            status = "executed" if d.executed else ("pending-approval" if d.pending_approval else "blocked/none")
            out.append(f"- {d.ts:%Y-%m-%d %H:%M} {verb} {tgt} [{status}] — {p.rationale[:80]}")
        return "\n".join(out) if out else "(no prior decisions)"
