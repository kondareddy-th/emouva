"""Harness configuration: model tiering, paths, and runtime mode.

Kept separate from the FastAPI app's `app.config` so the harness can run as a
standalone worker (`python -m app.harness.tick`) without importing the web app.
"""
from __future__ import annotations

import os
from pathlib import Path

# Load backend/.env (where ANTHROPIC_KEY lives) so the harness works as a worker.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

# --- Model tiering (see ARCHITECTURE.md §6) ------------------------------------
# Routine ticks use a cheaper/faster model; hard or large-notional decisions and
# strategy design escalate to Opus. Override per deployment via env.
MODEL_TICK = os.getenv("EMOUVA_MODEL_TICK", "claude-sonnet-5")
MODEL_DECISION = os.getenv("EMOUVA_MODEL_DECISION", "claude-opus-4-8")
MODEL_PRECHECK = os.getenv("EMOUVA_MODEL_PRECHECK", "claude-haiku-4-5-20251001")

# --- Where durable state lives -------------------------------------------------
# Per-user memory files (the memory-tool backend) and the decision journal.
# Defaults under the repo so the slice runs with zero setup; point at a mounted
# volume / object store in production.
DATA_ROOT = Path(os.getenv("EMOUVA_DATA_ROOT", Path(__file__).resolve().parents[2] / ".harness_data"))
MEMORY_ROOT = DATA_ROOT / "memory"      # MEMORY_ROOT/<user_id>/memories/...
JOURNAL_ROOT = DATA_ROOT / "journal"    # JOURNAL_ROOT/<user_id>.jsonl

# --- Anthropic ----------------------------------------------------------------
# Accept either ANTHROPIC_API_KEY (SDK default) or ANTHROPIC_KEY (used in our .env).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_KEY", "")

# Prompt-caching TTL for the stable per-user prefix. Ticks can be minutes apart,
# so "1h" keeps the system+policy+strategy prefix warm between ticks.
CACHE_TTL = os.getenv("EMOUVA_CACHE_TTL", "1h")

# Rough chars-per-token estimate, used only to report a context budget in
# dry-run mode (real runs read exact counts from the API usage object).
CHARS_PER_TOKEN = 4
