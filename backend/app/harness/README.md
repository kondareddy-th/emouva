# Emouva agent-trader harness (vertical slice)

A runnable, context-efficient per-user **decision tick**. See
[`../../../docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md) for the full design.

```
wake → load state JIT → build small CACHED context → brain proposes
     → safety gate → execute / enqueue approval → journal + memory → sleep
```

## Run it

```bash
cd backend
export PYTHONPATH=$PWD

# 1) Fully offline — no credentials. Proves wiring + flat context budget.
.venv/bin/python -m app.harness.tick --dry-run --ticks 3

# 2) Demo the safety gate
.venv/bin/python -m app.harness.tick --dry-run --approval-threshold 100   # → pending_approval
.venv/bin/python -m app.harness.tick --dry-run --kill-switch              # → blocked

# 3) Real model brain (needs key); still mock paper broker
ANTHROPIC_API_KEY=sk-... .venv/bin/python -m app.harness.tick --ticks 2

# 4) Real Alpaca paper account (needs `pip install alpaca-py` + paper keys)
ALPACA_API_KEY_ID=... ALPACA_API_SECRET_KEY=... \
  .venv/bin/python -m app.harness.tick --broker alpaca --dry-run

# 5) LIVE Robinhood agentic MCP — uses the SEPARATE agent venv (see below).
#    Requires: `/mcp` authenticated in Claude Code for this project.
PYTHONPATH=$PWD .venv-agent/bin/python -m app.harness.tick --broker robinhood --ticks 1
```

## Two virtualenvs (important)

`claude-agent-sdk` pulls `mcp` → newer `starlette`/`pydantic` that conflict with
the FastAPI backend, so the harness's live-MCP path is isolated:

| venv | used for | key deps |
|---|---|---|
| `backend/.venv` | the FastAPI app + harness `mock` / `stub` / `anthropic`-live modes | fastapi, sqlalchemy, anthropic, pydantic 2.10 |
| `backend/.venv-agent` | harness `--broker robinhood` (Agent SDK → Robinhood MCP) | claude-agent-sdk, anthropic, pydantic |

Run the Robinhood broker only from `.venv-agent`. Everything else runs from `.venv`.

Runtime state is written under `backend/.harness_data/` (gitignored):
`memory/<user>/memories/*.md` and `journal/<user>.jsonl`.

## File map

| File | Role |
|---|---|
| `state.py` | Typed contracts: `Policy`, `StrategySpec`, `PortfolioSnapshot`, `TradeProposal`, `GateDecision`, `Decision` |
| `config.py` | Model tiering, data paths, cache TTL |
| `memory_store.py` | **Memory-tool backend** — per-user `/memories` files, path-traversal safe |
| `brokers/` | `Broker` protocol · `MockBroker` (no creds) · `AlpacaPaperBroker` (optional) |
| `brain.py` | **Context-efficiency core** — cached stable prefix + small dynamic tail; Anthropic Messages API w/ prompt caching + forced `submit_decision` tool; offline `StubBrain` |
| `safety.py` | **SafetyGate** — kill switch, allowlist, per-trade/daily caps, concentration, approval threshold (code, not prompt) |
| `journal.py` | Append-only decision journal (JSONL → Postgres later) |
| `runner.py` | `AgentRunner.tick()` — orchestrates one tick |
| `tick.py` | CLI entry + demo user fixture |

## What's real vs. stubbed (slice v0.1)

| Real | Stubbed / next |
|---|---|
| Decision-tick flow, cached-prefix context, safety gate, memory+journal persistence | Brain falls back to a deterministic `StubBrain` without `ANTHROPIC_API_KEY` |
| Anthropic Messages API path with prompt caching + tool-use | `MockBroker` book is in-memory & resets per process |
| Alpaca paper adapter (when keys present) | Robinhood/Alpaca **MCP** adapter not wired yet (see below) |

## Where the live integrations plug in

- **Broker MCP (Robinhood/Alpaca):** add `brokers/mcp_broker.py` implementing the
  `Broker` protocol against the MCP tools (`get_portfolio`, `place_equity_order`…),
  injecting the user's OAuth bearer per call. The runner/gate are unchanged.
- **Agent SDK runtime:** swap `brain.decide()`'s API call for a `claude_agent_sdk.query()`
  to get subagents (research/backtest), MCP tool-search, and automatic compaction —
  for richer interactive flows. The hot tick can stay on the raw Messages API for
  minimal token control.
- **OAuth + per-user tokens, scheduler/cadence, approval queue + push:** live in the
  FastAPI app, not here.
