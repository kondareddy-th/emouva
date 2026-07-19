"""MCPBroker — live broker via the Robinhood (or Alpaca) **agentic MCP**.

This is the §3/§6 integration point: the harness's `Broker` protocol backed by
the real Robinhood agentic MCP tools.

Auth model (important):
  * TUNING / single user (now): reuses the `robinhood-trading` MCP connection you
    authenticated in Claude Code via `/mcp`. The Claude Agent SDK drives the
    Claude Code CLI, which already holds your per-user OAuth token — so we don't
    manage tokens here. Requires `pip install claude-agent-sdk` and a green
    `/mcp` auth in this project.
  * PRODUCTION / multi-user (later): our FastAPI runs OAuth per user, stores the
    bearer in the token vault, and injects it per `query()` via
    `mcpServers[...].headers.Authorization`. Same protocol, different token source.

Tool mapping (Robinhood agentic MCP):
    get_snapshot()  -> get_portfolio + get_equity_positions + get_equity_quotes
    place_order()   -> review_equity_order (preview) then place_equity_order

STATUS: scaffold. The read/exec calls run through the Agent SDK but have NOT been
live-verified yet (needs your `/mcp` auth). Treat as a starting point to tune.
"""
from __future__ import annotations

import asyncio
import json
import re

from ..state import PortfolioSnapshot, Position, Quote, TradeProposal, Action

# Robinhood agentic MCP tool surface we rely on (verified tool names).
_READ_TOOLS = [
    "mcp__robinhood-trading__get_portfolio",
    "mcp__robinhood-trading__get_equity_positions",
    "mcp__robinhood-trading__get_equity_quotes",
    "mcp__robinhood-trading__get_accounts",
]
_EXEC_TOOLS = [
    "mcp__robinhood-trading__review_equity_order",
    "mcp__robinhood-trading__place_equity_order",
]

_SNAPSHOT_PROMPT = """Use the robinhood-trading MCP tools to read the AGENTIC account state.
Call get_portfolio, get_equity_positions, and get_equity_quotes for these symbols: {symbols}.
Then reply with ONLY a single fenced ```json block, no prose, in EXACTLY this shape:
{{"cash": <num>, "buying_power": <num>, "equity": <num>,
  "positions": [{{"symbol": "X", "qty": <num>, "avg_price": <num>, "market_value": <num>}}],
  "quotes": [{{"symbol": "X", "price": <num>}}],
  "spent_today_usd": <num>}}"""


def _extract_json(text: str) -> dict:
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL) or re.search(r"(\{.*\})", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON found in agent output: {text[:200]}")
    return json.loads(m.group(1))


class MCPBroker:
    name = "robinhood-mcp"

    def __init__(self, user_id: str, server: str = "robinhood-trading"):
        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError as e:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "MCPBroker requires `pip install claude-agent-sdk` and a Robinhood "
                "MCP connection authenticated in Claude Code (`/mcp`). Use --broker mock "
                "to run without it."
            ) from e
        self.user_id = user_id
        self.server = server

    # --- Agent SDK bridge -----------------------------------------------------
    async def _run(self, prompt: str, allowed_tools: list[str]) -> str:
        """Run one Agent SDK query that may call the robinhood MCP tools; return final text."""
        from claude_agent_sdk import query, ClaudeAgentOptions

        options = ClaudeAgentOptions(
            # Reuse the project's MCP config + the /mcp OAuth token.
            setting_sources=["project"],
            allowed_tools=allowed_tools,
            permission_mode="acceptEdits",
        )
        final = ""
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "result"):
                final = message.result
        return final

    def _run_sync(self, prompt: str, allowed_tools: list[str]) -> str:
        return asyncio.run(self._run(prompt, allowed_tools))

    # --- Broker protocol ------------------------------------------------------
    def get_snapshot(self, symbols: list[str]) -> PortfolioSnapshot:
        out = self._run_sync(_SNAPSHOT_PROMPT.format(symbols=symbols or []), _READ_TOOLS)
        d = _extract_json(out)
        return PortfolioSnapshot(
            cash=d["cash"], buying_power=d["buying_power"], equity=d["equity"],
            positions=[Position(**p) for p in d.get("positions", [])],
            quotes=[Quote(**q) for q in d.get("quotes", [])],
            spent_today_usd=d.get("spent_today_usd", 0.0),
        )

    def place_order(self, proposal: TradeProposal) -> dict:
        if proposal.action is Action.HOLD or not proposal.symbol:
            return {"status": "noop"}
        # Preview first (review_equity_order), then place. The SafetyGate has
        # already approved by the time we get here.
        prompt = (
            f"Place a {proposal.action.value} order on the agentic account: "
            f"{proposal.qty} shares of {proposal.symbol}, "
            f"{proposal.order_type.value}"
            + (f" at limit {proposal.limit_price}" if proposal.limit_price else "")
            + ". First call review_equity_order to preview, then place_equity_order. "
            "Reply with ONLY a ```json block: {\"status\":..., \"order_id\":..., \"filled\":...}."
        )
        out = self._run_sync(prompt, _EXEC_TOOLS)
        try:
            return {"broker": self.name, **_extract_json(out)}
        except ValueError:
            return {"broker": self.name, "status": "unknown", "raw": out[:300]}
