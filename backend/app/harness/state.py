"""Typed state for the harness.

These models are the contract between layers: the broker produces a
PortfolioSnapshot, the brain produces a TradeProposal, the safety gate produces
a GateDecision, and the runner records a Decision. Everything is plain pydantic
so it serializes cleanly into the journal and over the API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


# --- Durable, per-user config (changes rarely -> cacheable prefix) -------------

class Policy(BaseModel):
    """User-set risk + autonomy policy. The hard guardrails the SafetyGate enforces."""
    user_id: str
    approval_threshold_usd: float = 500.0   # trades with notional above this need human approval
    per_trade_cap_usd: float = 2_000.0      # hard ceiling on a single order
    daily_spend_cap_usd: float = 5_000.0    # hard ceiling on buys per day
    max_position_pct: float = 0.25          # no single symbol above this fraction of equity
    cash_floor_pct: float = 0.10            # keep at least this fraction of equity in cash (dry powder)
    sector_cap_pct: float = 0.30            # no single sector above this fraction of equity
    max_orders_week: int = 3                # cap on buy orders placed in the trailing 7 days
    margin_of_safety_pct: float = 30.0      # required discount to conservative fair value before buying
    allowed_symbols: list[str] = Field(default_factory=list)  # empty = no allowlist restriction
    cadence_minutes: int = 60               # how often this agent wakes
    kill_switch: bool = False               # one flag halts all trading for this user


class StrategySpec(BaseModel):
    """The refined, backtested strategy the agent executes. Stable between ticks."""
    name: str
    objective: str                          # plain-language goal, e.g. "steady growth, low drawdown"
    rules: str                              # plain-language rules the model reasons over
    universe: list[str] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)


# --- Live, per-tick state (changes every tick -> NOT cached) -------------------

class Position(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    market_value: float
    sector: Optional[str] = None            # for the sector-cap check


class Quote(BaseModel):
    symbol: str
    price: float


class PortfolioSnapshot(BaseModel):
    as_of: datetime = Field(default_factory=_utcnow)
    cash: float
    buying_power: float
    equity: float
    positions: list[Position] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)
    spent_today_usd: float = 0.0
    orders_this_week: int = 0               # buy orders placed in the trailing 7 days (for max_orders_week)

    def price_of(self, symbol: str) -> Optional[float]:
        for q in self.quotes:
            if q.symbol == symbol:
                return q.price
        for p in self.positions:
            if p.symbol == symbol and p.qty:
                return p.market_value / p.qty
        return None


# --- Model output --------------------------------------------------------------

class TradeProposal(BaseModel):
    action: Action
    symbol: Optional[str] = None
    qty: float = 0.0
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    rationale: str = ""
    confidence: float = 0.0                 # 0..1

    def notional(self, snapshot: PortfolioSnapshot) -> float:
        if self.action is Action.HOLD or not self.symbol:
            return 0.0
        px = self.limit_price or snapshot.price_of(self.symbol) or 0.0
        return abs(self.qty) * px


# --- Gate + decision record ----------------------------------------------------

class GateDecision(BaseModel):
    allowed: bool                           # passed hard caps / allowlist / kill switch
    requires_approval: bool                 # notional over threshold -> human must confirm
    notional_usd: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    """Immutable journal record of one tick."""
    ts: datetime = Field(default_factory=_utcnow)
    user_id: str
    reason: str                             # why the agent woke (cadence / event)
    proposal: TradeProposal
    gate: GateDecision
    executed: bool = False
    pending_approval: bool = False
    broker_result: dict = Field(default_factory=dict)
    snapshot_summary: str = ""
    usage: dict = Field(default_factory=dict)  # context-budget telemetry
