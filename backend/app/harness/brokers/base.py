"""Broker protocol — the only broker surface the runner/safety layers know about.

Read methods feed the decision tick's state snapshot; `place_order` is the one
write the safety gate guards. A live Robinhood/Alpaca MCP adapter implements the
same protocol (the MCP tool calls map 1:1 onto these methods).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..state import PortfolioSnapshot, TradeProposal


@runtime_checkable
class Broker(Protocol):
    name: str

    def get_snapshot(self, symbols: list[str]) -> PortfolioSnapshot:
        """Account cash/equity/positions + quotes for `symbols`. Read-only."""
        ...

    def place_order(self, proposal: TradeProposal) -> dict:
        """Submit an order. Returns a broker result dict (id, status, filled_qty...)."""
        ...
