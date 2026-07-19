"""SafetyGate — the hard, code-level guardrail layer (ARCHITECTURE.md §7).

This is deliberately NOT a prompt. Robinhood's own approval is soft and
prompt-driven, so every threshold/cap/kill-switch decision is enforced here in
code, before any order reaches the broker.
"""
from __future__ import annotations

from .state import Action, GateDecision, Policy, PortfolioSnapshot, TradeProposal


class SafetyGate:
    def __init__(self, policy: Policy):
        self.policy = policy

    def evaluate(self, proposal: TradeProposal, snapshot: PortfolioSnapshot,
                 proposed_sector: str | None = None) -> GateDecision:
        p = self.policy
        reasons: list[str] = []
        notional = proposal.notional(snapshot)

        # HOLD always passes, nothing to execute.
        if proposal.action is Action.HOLD:
            return GateDecision(allowed=True, requires_approval=False, notional_usd=0.0,
                                reasons=["hold — no order"])

        allowed = True

        # 1. Kill switch halts everything.
        if p.kill_switch:
            allowed = False
            reasons.append("kill switch engaged")

        # 2. Allowlist (empty = unrestricted).
        if p.allowed_symbols and proposal.symbol not in p.allowed_symbols:
            allowed = False
            reasons.append(f"{proposal.symbol} not in allowed_symbols")

        # 3. Per-trade hard cap.
        if notional > p.per_trade_cap_usd:
            allowed = False
            reasons.append(f"notional ${notional:,.0f} exceeds per-trade cap ${p.per_trade_cap_usd:,.0f}")

        # 4. Daily spend cap (buys only).
        if proposal.action is Action.BUY and snapshot.spent_today_usd + notional > p.daily_spend_cap_usd:
            allowed = False
            reasons.append(
                f"daily spend ${snapshot.spent_today_usd + notional:,.0f} exceeds cap ${p.daily_spend_cap_usd:,.0f}"
            )

        # 5. Max single-position concentration (buys only).
        if proposal.action is Action.BUY and snapshot.equity > 0:
            held = next((pos.market_value for pos in snapshot.positions if pos.symbol == proposal.symbol), 0.0)
            projected_pct = (held + notional) / snapshot.equity
            if projected_pct > p.max_position_pct:
                allowed = False
                reasons.append(
                    f"{proposal.symbol} would be {projected_pct:.0%} of equity (cap {p.max_position_pct:.0%})"
                )

        # 6. Funds check (buys only).
        if proposal.action is Action.BUY and notional > snapshot.buying_power:
            allowed = False
            reasons.append(f"notional ${notional:,.0f} exceeds buying power ${snapshot.buying_power:,.0f}")

        # 7. Cash floor — a buy may not draw cash below the reserve (buys only).
        if proposal.action is Action.BUY and p.cash_floor_pct > 0 and snapshot.equity > 0:
            floor = p.cash_floor_pct * snapshot.equity
            if snapshot.cash - notional < floor:
                allowed = False
                reasons.append(
                    f"cash would fall to ${snapshot.cash - notional:,.0f}, below the {p.cash_floor_pct:.0%} floor "
                    f"(${floor:,.0f})"
                )

        # 8. Sector cap — a buy may not push its sector above the cap (buys only).
        if proposal.action is Action.BUY and p.sector_cap_pct > 0 and snapshot.equity > 0 and proposed_sector:
            sector_mv = sum(pos.market_value for pos in snapshot.positions if pos.sector == proposed_sector)
            projected_pct = (sector_mv + notional) / snapshot.equity
            if projected_pct > p.sector_cap_pct:
                allowed = False
                reasons.append(
                    f"{proposed_sector} would be {projected_pct:.0%} of equity (sector cap {p.sector_cap_pct:.0%})"
                )

        # 9. Trading pace — cap on buy orders in the trailing 7 days (buys only).
        if proposal.action is Action.BUY and p.max_orders_week > 0 and snapshot.orders_this_week >= p.max_orders_week:
            allowed = False
            reasons.append(
                f"already placed {snapshot.orders_this_week} buys this week (cap {p.max_orders_week})"
            )

        # Human approval required when an otherwise-allowed trade is large.
        requires_approval = allowed and notional > p.approval_threshold_usd
        if requires_approval:
            reasons.append(
                f"notional ${notional:,.0f} over approval threshold ${p.approval_threshold_usd:,.0f} — needs user OK"
            )
        if allowed and not requires_approval and not reasons:
            reasons.append("within all limits — auto-execute")

        return GateDecision(
            allowed=allowed,
            requires_approval=requires_approval,
            notional_usd=round(notional, 2),
            reasons=reasons,
        )
