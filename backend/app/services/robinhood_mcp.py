"""Minimal MCP client for the Robinhood agentic server, over raw httpx.

We can't use the official `mcp` SDK here — it pulls a newer starlette/pydantic
that breaks FastAPI 0.115. So this speaks the MCP Streamable-HTTP protocol
directly: initialize -> notifications/initialized -> tools/call. Just enough to
read the agentic account with a user's OAuth bearer token.

Tool surface used (verified names): get_portfolio, get_equity_positions,
get_equity_quotes. Read-only here; order placement lives in the harness path.
"""
from __future__ import annotations

import json

import httpx

from .robinhood_oauth import RESOURCE

PROTOCOL_VERSION = "2025-06-18"
_CLIENT_INFO = {"name": "emouva", "version": "0.1"}


class MCPError(Exception):
    pass


def _parse(resp: httpx.Response) -> dict:
    """Return the JSON-RPC payload from a JSON or SSE response."""
    ct = resp.headers.get("content-type", "")
    if "text/event-stream" in ct:
        payload = None
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                payload = json.loads(line[5:].strip())
        if payload is None:
            raise MCPError(f"Empty SSE response: {resp.text[:200]}")
    else:
        payload = resp.json()
    if isinstance(payload, dict) and payload.get("error"):
        raise MCPError(str(payload["error"]))
    return payload


class RobinhoodMCP:
    """One short-lived MCP session per logical operation (stateless across calls)."""

    def __init__(self, access_token: str):
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self._session_id: str | None = None
        self._id = 0

    async def _rpc(self, client: httpx.AsyncClient, method: str,
                   params: dict | None = None, notify: bool = False) -> dict | None:
        self._id += 1
        body: dict = {"jsonrpc": "2.0", "method": method}
        if not notify:
            body["id"] = self._id
        if params is not None:
            body["params"] = params
        headers = dict(self._headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        resp = await client.post(RESOURCE, json=body, headers=headers)
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
        if resp.status_code == 401:
            raise MCPError("unauthorized — token expired or invalid")
        resp.raise_for_status()
        return None if notify else _parse(resp)

    async def list_tools(self) -> list[dict]:
        """All tools the server exposes, each with name/description/inputSchema.
        Used to confirm the exact order-tool arg schema before live placement."""
        async with httpx.AsyncClient(timeout=30) as client:
            await self._rpc(client, "initialize", {
                "protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": _CLIENT_INFO,
            })
            await self._rpc(client, "notifications/initialized", notify=True)
            payload = await self._rpc(client, "tools/list", {})
        return (payload or {}).get("result", {}).get("tools", [])

    async def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            await self._rpc(client, "initialize", {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": _CLIENT_INFO,
            })
            await self._rpc(client, "notifications/initialized", notify=True)
            payload = await self._rpc(client, "tools/call",
                                      {"name": name, "arguments": arguments or {}})
        result = (payload or {}).get("result", {})
        if result.get("isError"):
            raise MCPError(f"tool {name} error: {result}")
        return self._tool_json(result)

    @staticmethod
    def _tool_json(result: dict) -> dict:
        """Tool results arrive as content blocks; pull structured JSON out of the text."""
        # Prefer structuredContent if the server provides it.
        if isinstance(result.get("structuredContent"), dict):
            return result["structuredContent"]
        for block in result.get("content", []):
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except (json.JSONDecodeError, KeyError):
                    return {"text": block.get("text", "")}
        return {}

    # --- convenience reads ----------------------------------------------------
    async def get_accounts(self) -> dict:
        return await self.call_tool("get_accounts")

    async def get_portfolio(self, account_number: str) -> dict:
        return await self.call_tool("get_portfolio", {"account_number": account_number})

    async def get_positions(self, account_number: str) -> dict:
        return await self.call_tool("get_equity_positions", {"account_number": account_number})

    async def get_quotes(self, symbols: list[str]) -> dict:
        return await self.call_tool("get_equity_quotes", {"symbols": symbols})

    # --- order placement (P3 live) --------------------------------------------
    # These forward a caller-built args dict so the exact order-tool arg schema
    # lives in ONE place (app/services/agent/broker.py::_robinhood_place) and can
    # be corrected against the live tool definitions before real-money use.
    async def review_equity_order(self, args: dict) -> dict:
        """Preview an equity order (no placement). Call before place_equity_order."""
        return await self.call_tool("review_equity_order", args)

    async def place_equity_order(self, args: dict) -> dict:
        """Place an equity order on the agentic account. REAL MONEY."""
        return await self.call_tool("place_equity_order", args)


def list_accounts(accounts_result: dict) -> list[dict]:
    """Extract the accounts array from a get_accounts() result."""
    return (accounts_result or {}).get("data", {}).get("accounts", []) or accounts_result.get("accounts", [])


def pick_account(accounts: list[dict], account_number: str | None = None,
                 prefer_agentic: bool = False) -> dict | None:
    """Choose an account: explicit number > agentic (if asked) > default > first active."""
    active = [a for a in accounts if a.get("state") == "active" and not a.get("deactivated")]
    if account_number:
        return next((a for a in active if a.get("account_number") == account_number), None)
    if prefer_agentic:
        ag = next((a for a in active if (a.get("nickname") or "").lower() == "agentic"
                   or a.get("agentic_allowed")), None)
        if ag:
            return ag
    return next((a for a in active if a.get("is_default")), None) or (active[0] if active else None)
