"""Emouva agent-trader harness.

A context-efficient, per-user decision loop: each tick cold-starts a small,
cache-friendly context, loads durable state just-in-time, asks the model for a
trade proposal, runs it through a hard safety gate, executes on a broker, and
journals the decision. See docs/ARCHITECTURE.md for the design.
"""

from .state import (
    Policy,
    StrategySpec,
    Position,
    PortfolioSnapshot,
    Quote,
    TradeProposal,
    GateDecision,
    Decision,
)

__all__ = [
    "Policy",
    "StrategySpec",
    "Position",
    "PortfolioSnapshot",
    "Quote",
    "TradeProposal",
    "GateDecision",
    "Decision",
]
