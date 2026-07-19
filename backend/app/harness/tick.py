"""CLI: run one (or a few) decision ticks for a demo user.

    # fully offline, no credentials — proves the wiring + context budget
    python -m app.harness.tick --dry-run --ticks 3

    # real model (needs ANTHROPIC_API_KEY), still mock paper broker
    ANTHROPIC_API_KEY=sk-... python -m app.harness.tick --ticks 2

    # real Alpaca paper account (needs alpaca-py + ALPACA_API_KEY_ID/SECRET)
    python -m app.harness.tick --broker alpaca --dry-run
"""
from __future__ import annotations

import argparse
import json

from . import config
from .brokers import get_broker
from .journal import Journal
from .memory_store import MemoryStore
from .runner import AgentRunner
from .state import Policy, StrategySpec


def demo_policy(user_id: str) -> Policy:
    return Policy(
        user_id=user_id,
        approval_threshold_usd=500.0,
        per_trade_cap_usd=2_000.0,
        daily_spend_cap_usd=5_000.0,
        max_position_pct=0.25,
        allowed_symbols=[],          # unrestricted for the demo
        cadence_minutes=60,
        kill_switch=False,
    )


def demo_strategy() -> StrategySpec:
    return StrategySpec(
        name="steady-accumulation",
        objective="Steady long-term growth with low drawdown; no leverage, long only.",
        universe=["AAPL", "MSFT", "NVDA", "SPY", "TSLA"],
        rules=(
            "- Long only. Accumulate in small tranches (~2% of equity).\n"
            "- Keep no single name above 25% of equity.\n"
            "- Prefer adding to in-universe names trading below recent levels.\n"
            "- Hold when nothing is compelling; cash is a position."
        ),
        params={"tranche_pct": 0.02, "max_names": 8},
    )


def _print_tick(i: int, d) -> None:
    p, g = d.proposal, d.gate
    print(f"\n=== tick {i} ({d.reason}) =========================================")
    print(f"context budget : {json.dumps(d.usage)}")
    print(f"proposal       : {p.action.value.upper()} "
          f"{(str(p.qty) + ' ' + p.symbol) if p.symbol else ''}"
          f"  (conf {p.confidence:.2f})")
    print(f"  rationale    : {p.rationale}")
    print(f"gate           : allowed={g.allowed} approval={g.requires_approval} "
          f"notional=${g.notional_usd:,.0f}")
    for r in g.reasons:
        print(f"   - {r}")
    print(f"result         : {json.dumps(d.broker_result)}")
    print(f"  executed={d.executed}  pending_approval={d.pending_approval}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run emouva agent-trader decision ticks.")
    ap.add_argument("--user", default="demo")
    ap.add_argument("--broker", default="mock", choices=["mock", "alpaca", "robinhood"])
    ap.add_argument("--reason", default="cadence")
    ap.add_argument("--ticks", type=int, default=1)
    ap.add_argument("--model", default=None, help="override model id")
    ap.add_argument("--dry-run", action="store_true", help="use the offline stub brain")
    ap.add_argument("--approval-threshold", type=float, default=None,
                    help="override approval threshold (USD) to demo the approval path")
    ap.add_argument("--kill-switch", action="store_true", help="engage the kill switch to demo blocking")
    args = ap.parse_args()

    policy = demo_policy(args.user)
    if args.approval_threshold is not None:
        policy.approval_threshold_usd = args.approval_threshold
    if args.kill_switch:
        policy.kill_switch = True
    strategy = demo_strategy()
    broker = get_broker(args.broker, args.user)
    memory = MemoryStore(args.user)
    journal = Journal(args.user)
    runner = AgentRunner(policy, strategy, broker, memory, journal)

    mode = "DRY-RUN (stub brain)" if (args.dry_run or not config.ANTHROPIC_API_KEY) else "LIVE (Anthropic)"
    print(f"emouva harness · user={args.user} · broker={broker.name} · {mode}")

    for i in range(1, args.ticks + 1):
        if hasattr(broker, "tick"):
            broker.tick = i  # advance the mock price clock
        decision = runner.tick(reason=args.reason, model=args.model, dry_run=args.dry_run)
        _print_tick(i, decision)

    print(f"\njournal: {journal.path}")
    print(f"memory : {memory.root / 'memories'}")


if __name__ == "__main__":
    main()
