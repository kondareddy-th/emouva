"""AgentRunner — orchestrates ONE decision tick (ARCHITECTURE.md §4).

    wake -> load state JIT -> build small cached context -> brain proposes
         -> safety gate -> execute / enqueue approval -> journal + memory -> sleep

The runner holds no long-lived conversation: each tick is self-contained, which
is exactly what keeps per-tick context cost bounded.
"""
from __future__ import annotations

from . import config
from .brain import build_context, decide
from .brokers.base import Broker
from .journal import Journal
from .memory_store import MemoryStore
from .safety import SafetyGate
from .state import Action, Decision, Policy, StrategySpec


class AgentRunner:
    def __init__(self, policy: Policy, strategy: StrategySpec, broker: Broker,
                 memory: MemoryStore, journal: Journal):
        self.policy = policy
        self.strategy = strategy
        self.broker = broker
        self.memory = memory
        self.journal = journal
        self.gate = SafetyGate(policy)

    def tick(self, reason: str = "cadence", model: str | None = None, dry_run: bool = False) -> Decision:
        model = model or config.MODEL_TICK

        # 1. Load live + durable state just-in-time (small).
        snapshot = self.broker.get_snapshot(self.strategy.universe)
        recap = self.journal.tail_summary(n=5)

        # 2. Build the cache-friendly context and ask the brain for one action.
        bundle = build_context(self.policy, self.strategy, snapshot, recap)
        proposal, usage = decide(bundle, snapshot, self.strategy, model=model, dry_run=dry_run)

        # 3. Hard safety gate (code, not prompt).
        gate = self.gate.evaluate(proposal, snapshot)

        # 4. Act: execute, enqueue for approval, or no-op.
        executed = pending = False
        result: dict = {}
        if proposal.action is Action.HOLD:
            result = {"status": "hold"}
        elif not gate.allowed:
            result = {"status": "blocked", "reasons": gate.reasons}
        elif gate.requires_approval:
            pending = True
            result = {"status": "pending_approval"}
            # In production: push notification + write to the approval queue.
            self.memory.save(
                "/memories/pending_approval.md",
                f"PENDING: {proposal.action.value} {proposal.qty:g} {proposal.symbol} "
                f"(${gate.notional_usd:,.0f})\nrationale: {proposal.rationale}\n",
            )
        else:
            result = self.broker.place_order(proposal)
            executed = result.get("status") not in ("noop", None)

        # 5. Journal + memory (durable, for the next tick's JIT recall).
        decision = Decision(
            user_id=self.policy.user_id, reason=reason, proposal=proposal, gate=gate,
            executed=executed, pending_approval=pending, broker_result=result,
            snapshot_summary=(
                f"equity ${snapshot.equity:,.0f}, cash ${snapshot.cash:,.0f}, "
                f"{len(snapshot.positions)} positions"
            ),
            usage=usage,
        )
        self.journal.append(decision)
        self.memory.save(
            "/memories/last_tick.md",
            f"# Last tick ({decision.ts:%Y-%m-%d %H:%M}Z)\n"
            f"action: {proposal.action.value} {proposal.qty:g} {proposal.symbol or ''}\n"
            f"executed: {executed}  pending_approval: {pending}\n"
            f"rationale: {proposal.rationale}\n"
            f"gate: {'; '.join(gate.reasons)}\n",
        )
        return decision
