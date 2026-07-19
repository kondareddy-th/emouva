"""AlpacaPaperBroker — real paper trading via Alpaca's paper API.

Optional adapter (requires `alpaca-py` + paper keys). Same protocol as MockBroker,
so the runner is unchanged. Alpaca paper is identical to live except orders are
not routed to a real exchange, which is exactly what we want for the
fake-money stage of the strategy lifecycle (ARCHITECTURE.md §5).

Env:
    ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY   (paper keys)
"""
from __future__ import annotations

import os

from ..state import Position, PortfolioSnapshot, Quote, TradeProposal, Action, OrderType


class AlpacaPaperBroker:
    name = "alpaca-paper"

    def __init__(self, user_id: str):
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient
        except ImportError as e:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "AlpacaPaperBroker requires `pip install alpaca-py`. "
                "Use --broker mock to run without it."
            ) from e

        key = os.getenv("ALPACA_API_KEY_ID")
        secret = os.getenv("ALPACA_API_SECRET_KEY")
        if not (key and secret):
            raise RuntimeError("Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY (paper keys).")

        self.user_id = user_id
        self._trading = TradingClient(key, secret, paper=True)
        self._data = StockHistoricalDataClient(key, secret)

    def get_snapshot(self, symbols: list[str]) -> PortfolioSnapshot:
        from alpaca.data.requests import StockLatestQuoteRequest

        acct = self._trading.get_account()
        positions = [
            Position(
                symbol=p.symbol,
                qty=float(p.qty),
                avg_price=float(p.avg_entry_price),
                market_value=float(p.market_value),
            )
            for p in self._trading.get_all_positions()
        ]
        watch = sorted(set(symbols) | {p.symbol for p in positions})
        quotes: list[Quote] = []
        if watch:
            latest = self._data.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=watch))
            for sym, q in latest.items():
                price = float(getattr(q, "ask_price", 0) or getattr(q, "bid_price", 0) or 0)
                quotes.append(Quote(symbol=sym, price=price))
        return PortfolioSnapshot(
            cash=float(acct.cash),
            buying_power=float(acct.buying_power),
            equity=float(acct.equity),
            positions=positions,
            quotes=quotes,
        )

    def place_order(self, proposal: TradeProposal) -> dict:
        if proposal.action is Action.HOLD or not proposal.symbol:
            return {"status": "noop"}
        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        side = OrderSide.BUY if proposal.action is Action.BUY else OrderSide.SELL
        if proposal.order_type is OrderType.LIMIT and proposal.limit_price:
            req = LimitOrderRequest(
                symbol=proposal.symbol, qty=proposal.qty, side=side,
                time_in_force=TimeInForce.DAY, limit_price=proposal.limit_price,
            )
        else:
            req = MarketOrderRequest(
                symbol=proposal.symbol, qty=proposal.qty, side=side,
                time_in_force=TimeInForce.DAY,
            )
        order = self._trading.submit_order(req)
        return {
            "status": str(order.status),
            "broker": self.name,
            "order_id": str(order.id),
            "symbol": proposal.symbol,
            "side": proposal.action.value,
            "qty": proposal.qty,
        }
