"""MockBroker — deterministic, zero-credential paper book.

Lets the whole tick run end-to-end with no external services, so the context
design can be validated offline. Prices are derived deterministically from the
symbol (stable across runs, with a small reproducible wobble) — no randomness,
no network.
"""
from __future__ import annotations

import hashlib

from ..state import Position, PortfolioSnapshot, Quote, TradeProposal, Action


def _base_price(symbol: str) -> float:
    h = int(hashlib.sha256(symbol.encode()).hexdigest(), 16)
    return round(20 + (h % 48000) / 100, 2)  # ~$20–$500, stable per symbol


def _wobble(symbol: str, tick: int) -> float:
    # deterministic +/- few-percent oscillation so successive ticks differ
    h = int(hashlib.sha256(f"{symbol}:{tick}".encode()).hexdigest(), 16)
    return 1 + ((h % 800) - 400) / 10000  # +/-4%


class MockBroker:
    name = "mock"

    def __init__(self, user_id: str, tick: int = 0):
        self.user_id = user_id
        self.tick = tick
        # a small seeded book: some cash + two starter positions
        self._positions = {
            "AAPL": 10.0,
            "MSFT": 5.0,
        }
        self._cash = 100_000.0
        self._spent_today = 0.0

    def get_snapshot(self, symbols: list[str]) -> PortfolioSnapshot:
        watch = sorted(set(symbols) | set(self._positions))
        quotes = [Quote(symbol=s, price=round(_base_price(s) * _wobble(s, self.tick), 2)) for s in watch]
        price = {q.symbol: q.price for q in quotes}
        positions = [
            Position(
                symbol=s,
                qty=qty,
                avg_price=_base_price(s),
                market_value=round(qty * price[s], 2),
            )
            for s, qty in self._positions.items()
        ]
        equity = self._cash + sum(p.market_value for p in positions)
        return PortfolioSnapshot(
            cash=self._cash,
            buying_power=self._cash,
            equity=round(equity, 2),
            positions=positions,
            quotes=quotes,
            spent_today_usd=self._spent_today,
        )

    def place_order(self, proposal: TradeProposal) -> dict:
        if proposal.action is Action.HOLD or not proposal.symbol:
            return {"status": "noop"}
        px = proposal.limit_price or round(_base_price(proposal.symbol) * _wobble(proposal.symbol, self.tick), 2)
        notional = round(abs(proposal.qty) * px, 2)
        sign = 1 if proposal.action is Action.BUY else -1
        self._positions[proposal.symbol] = self._positions.get(proposal.symbol, 0.0) + sign * proposal.qty
        self._cash -= sign * notional
        if proposal.action is Action.BUY:
            self._spent_today += notional
        return {
            "status": "filled",
            "broker": self.name,
            "symbol": proposal.symbol,
            "side": proposal.action.value,
            "qty": proposal.qty,
            "fill_price": px,
            "notional": notional,
        }
