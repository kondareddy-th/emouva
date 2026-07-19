import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, Date, ForeignKey,
    Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Short, stable, non-enumerable public handle (u_ + 12 crockford b32). The
    # internal UUID stays the FK everywhere; public_id is what we show/return.
    public_id = Column(String(16), unique=True, nullable=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    robinhood_connected = Column(Boolean, default=False, nullable=False)
    tier = Column(String(20), default="free", nullable=False, server_default="free")  # "free" | "premium" (legacy; everything is free now)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    buy_rules = relationship("BuyRule", back_populates="user", lazy="noload")
    executions = relationship("Execution", back_populates="user", lazy="noload")
    notifications = relationship("Notification", back_populates="user", lazy="noload")


class RobinhoodConnection(Base):
    """Per-user Robinhood agentic-MCP OAuth tokens (encrypted at rest)."""
    __tablename__ = "robinhood_connections"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    client_id = Column(String(255), nullable=False)
    access_token_enc = Column(Text, nullable=False)
    refresh_token_enc = Column(Text, nullable=True)
    scope = Column(String(100), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Account(Base):
    """Any account whose positions we store for a user — generalized so a new
    account type is just a new ``kind``:

      kind='paper'     source_of_truth='internal'  — simulated; WE own cash+positions
      kind='agentic'   source_of_truth='broker'    — the fenced Robinhood account
      kind='robinhood' source_of_truth='broker'    — any other real RH account

    For broker accounts the broker is authoritative — the user can trade there
    directly, so we reconcile (sync) positions + cash from Robinhood periodically
    (``last_synced_at``). For paper accounts our DB is the source of truth.

    account_number is the join key everywhere: ``{username}-paper`` for paper,
    the broker's number (e.g. 912656568) for real accounts. Multi-account per
    user is native — nothing here is paper- or Robinhood-specific."""
    __tablename__ = "accounts"
    __table_args__ = (Index("ix_accounts_user", "user_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account_number = Column(String(80), unique=True, nullable=False, index=True)
    kind = Column(String(20), nullable=False, default="paper")            # paper | agentic | robinhood
    source_of_truth = Column(String(20), nullable=False, default="internal")  # internal | broker
    nickname = Column(String(60), nullable=False, default="")
    cash = Column(Float, nullable=False, default=0.0)                     # settled cash (owned=paper / synced=broker)
    buying_power = Column(Float, nullable=True)
    equity = Column(Float, nullable=True)                                 # last-known total value
    starting_cash = Column(Float, nullable=True)                          # paper only
    realized_pnl = Column(Float, nullable=False, default=0.0)             # paper only
    active = Column(Boolean, nullable=False, default=True)
    last_synced_at = Column(DateTime, nullable=True)                      # broker accounts: last reconcile
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    positions = relationship("AccountPosition", back_populates="account", lazy="noload",
                             cascade="all, delete-orphan", passive_deletes=True)


class AccountPosition(Base):
    """One open lot per symbol in an account — the generic holdings store for
    EVERY account kind. Paper fills write here directly; broker syncs overwrite
    it from Robinhood. Valued at live quotes at read time."""
    __tablename__ = "account_positions"
    __table_args__ = (
        UniqueConstraint("account_id", "symbol", name="uq_account_position_acct_symbol"),
        Index("ix_account_positions_acct", "account_id"),
        Index("ix_account_positions_user", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)   # denormalized for per-user queries
    symbol = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)
    avg_cost = Column(Float, nullable=False, default=0.0)
    last_price = Column(Float, nullable=True)                             # last mark we stored (from sync)
    source = Column(String(24), nullable=False, default="agent_fill")     # agent_fill | broker_sync | reconcile
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="positions", lazy="noload")


class AccountDeposit(Base):
    """A deposit into an account — paper accounts only for now (live funding goes
    through Robinhood). Increases the account's cash AND its funded baseline
    (starting_cash), so deposits don't read as gains. Audit trail of funding."""
    __tablename__ = "account_deposits"
    __table_args__ = (Index("ix_account_deposits_acct", "account_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    kind = Column(String(20), nullable=False, default="paper")   # paper (extensible)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Thesis(Base):
    """The Living Thesis for a holding or tracked idea — the written reason to own
    it, armed with machine-checkable downward triggers (falsifiers) and the
    adversarial red-team it survived on entry. Evaluated daily; the moment a
    falsifier trips the agent reviews whether it still earns its place."""
    __tablename__ = "theses"
    __table_args__ = (Index("ix_theses_user_status", "user_id", "status"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account = Column(String(80), nullable=False)
    symbol = Column(String(20), nullable=False)
    kind = Column(String(12), nullable=False, default="holding")     # holding | track
    thesis_text = Column(Text, nullable=False, default="")
    falsifiers = Column(JSONB, nullable=False, default=list)          # [{metric, comparator, threshold, source, label}]
    red_team = Column(JSONB, nullable=False, default=list)            # [{lens, attack, verdict}]
    fv_snapshot = Column(JSONB, nullable=True)                        # fair value at entry
    status = Column(String(12), nullable=False, default="active")     # active | flashed | broken | closed
    tripped = Column(JSONB, nullable=True)                            # which falsifier(s) last flashed
    order_id = Column(UUID(as_uuid=True), nullable=True)              # the entry (or exit-proposal) order
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_eval_at = Column(DateTime, nullable=True)


class Opportunity(Base):
    """The central, SHARED, pre-reasoned opportunity pool — the "secret engine".
    Global (one row per symbol). Each name is analyzed ONCE (thesis + falsifiers +
    4-lens red-team + growth) and every user's agent REUSES that reasoning rather
    than re-deriving it per account. Admin-only; regular users never see it.

    Flow: discovered → FV/margin enrich → cheap STATS gate → (only if stats good)
    harness analysis → category. category 1 = looks good + we understand the
    business (tradeable). category 2 = looks good but not understood (admins feed
    it info via chat → re-analyze → drop / promote / keep). rejected = didn't pass."""
    __tablename__ = "opportunities"
    __table_args__ = (Index("ix_opportunities_category", "category"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=True)
    sector = Column(String(60), nullable=True)
    source = Column(String(24), nullable=False, default="scan_losers")   # why it surfaced
    last_price = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)
    pct_change = Column(Float, nullable=True)
    fv_low = Column(Float, nullable=True)
    fv_base = Column(Float, nullable=True)
    fv_high = Column(Float, nullable=True)
    fv_conservative = Column(Float, nullable=True)
    fv_confident = Column(Boolean, nullable=False, default=False)
    margin_pct = Column(Float, nullable=True)
    # ── stats gate + central reasoning (reused across all users) ──
    stats = Column(JSONB, nullable=True)                                 # the quantitative snapshot used to gate
    stats_pass = Column(Boolean, nullable=True)                         # passed the cheap quality/growth gate?
    central_thesis = Column(Text, nullable=True)
    falsifiers = Column(JSONB, nullable=True)                           # [{metric, comparator, threshold, label}]
    red_team = Column(JSONB, nullable=True)                             # [{lens, attack, verdict}]
    growth = Column(Text, nullable=True)                                # near-term growth-potential assessment
    future_growth = Column(Text, nullable=True)                         # 5–10yr durability / dominance runway
    growth_exception = Column(Boolean, nullable=False, default=False)   # fairly-valued exceptional grower — keep despite no margin, user decides
    understood = Column(Boolean, nullable=True)                         # do we understand the business w/ available info?
    category = Column(Integer, nullable=True)                           # 1 (tradeable/confident) | 2 (hard to understand) | 0 (rejected) | null (unanalyzed)
    score = Column(Float, nullable=True)                                # 0–100 quality-first composite (compute-once, reused by every agent)
    sector_rank = Column(Integer, nullable=True)                        # 1 = best-scored confident name in its sector
    admin_notes = Column(Text, nullable=True)                           # info admins fed the harness (persisted, reused on re-analysis)
    analysis_status = Column(String(20), nullable=False, default="pending")  # pending | rejected_stats | analyzed
    status = Column(String(16), nullable=False, default="candidate")     # candidate | stale
    surfaced_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_analyzed_at = Column(DateTime, nullable=True)
    last_priced_at = Column(DateTime, nullable=True)
    meta = Column(JSONB, nullable=True)


# ── Polytrade: thematic auto-managed baskets (see docs/POLYTRADE.md) ──
# A Theme is a narrative-driven bet carrying a Living Thesis (narrative + falsifiers +
# red-team) and a basket of vetted names with target weights. It's the CENTRAL, shared
# object; per-user capital lives in ThemeAllocation. Constituents are drawn from the
# Opportunity pool, monitored via the same news/earnings cadence, and executed through
# the existing broker. `target_version` is the propagation contract: it bumps on every
# basket change and each allocation reconciles from its applied_version → target_version.

class Theme(Base):
    """A curated, AI-managed thematic basket (the central, shared object). Originated
    with an LLM-written narrative, a hero stat, machine-/news-checkable falsifiers and a
    4-lens red-team; monitored daily; auto-exits every allocation when the thesis breaks."""
    __tablename__ = "themes"
    __table_args__ = (Index("ix_themes_status", "status"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(90), unique=True, nullable=False, index=True)
    title = Column(String(140), nullable=False)
    tags = Column(JSONB, nullable=False, default=list)                   # ["AI","semis"]
    narrative = Column(Text, nullable=False, default="")                 # the thesis paragraph
    hero_stat = Column(Text, nullable=True)                              # "TSMC 50% growth through 2029" (LLM sometimes writes longer)
    status = Column(String(16), nullable=False, default="draft")         # draft|live|weakening|breaking|closed
    conviction = Column(Integer, nullable=False, default=50)             # 0..100 — the "price" users watch
    health = Column(String(12), nullable=False, default="strong")        # strong|watching|breaking
    falsifiers = Column(JSONB, nullable=False, default=list)             # [{label, breaks_if, kind, metric?, comparator?, threshold?}]
    red_team = Column(JSONB, nullable=False, default=list)               # [{lens, attack, verdict}] — demand/supply/valuation/catalyst
    target_version = Column(Integer, nullable=False, default=1)          # bumps on every basket (constituent/weight) change
    perf_snapshot = Column(JSONB, nullable=True)                         # since-inception %, 30d %, drawdown
    seed_narrative = Column(Text, nullable=True)                         # admin's seed input
    created_by = Column(String(120), nullable=True)                      # admin email
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_thesis_run_at = Column(DateTime, nullable=True)
    meta = Column(JSONB, nullable=True)

    constituents = relationship("ThemeConstituent", back_populates="theme", lazy="noload",
                                cascade="all, delete-orphan", passive_deletes=True)


class ThemeConstituent(Base):
    """One name in a theme's basket, with its target weight (weights within a theme sum
    to 1.0) and role. Provenance is the vetted Opportunity pool — a stock can only enter
    a theme if we've already reasoned about the business."""
    __tablename__ = "theme_constituents"
    __table_args__ = (
        UniqueConstraint("theme_id", "symbol", name="uq_theme_constituent"),
        Index("ix_theme_constituents_theme", "theme_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(20), nullable=False)
    target_weight = Column(Float, nullable=False, default=0.0)           # 0..1 (basket sums to 1)
    role = Column(String(12), nullable=False, default="satellite")       # anchor|satellite|speculative
    conviction = Column(Integer, nullable=True)                          # 0..100 raw pick conviction (pre-weighting)
    rationale = Column(Text, nullable=True)
    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=True)
    status = Column(String(10), nullable=False, default="active")        # active|exited
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    exited_at = Column(DateTime, nullable=True)

    theme = relationship("Theme", back_populates="constituents", lazy="noload")


class ThemeAllocation(Base):
    """Per-user capital committed to a theme (defined now; wired to the cash sweep +
    reconciler in M2). `applied_version` tracks how far this allocation has been
    reconciled toward the theme's `target_version`."""
    __tablename__ = "theme_allocations"
    __table_args__ = (
        Index("ix_theme_allocations_user", "user_id"),
        Index("ix_theme_allocations_theme", "theme_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account = Column(String(80), nullable=False)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    committed_usd = Column(Float, nullable=False, default=0.0)            # original sweep amount (immutable ref)
    cash = Column(Float, nullable=False, default=0.0)                     # uninvested cash held by the allocation
    invested_usd = Column(Float, nullable=False, default=0.0)             # deployed cost basis (= Σ holding cost)
    status = Column(String(12), nullable=False, default="pending")       # pending|active|unwinding|closed
    applied_version = Column(Integer, nullable=False, default=0)         # reconciled up to this theme.target_version
    market_value = Column(Float, nullable=True)                          # last-computed holdings MV (+ cash)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    unrealized_pnl = Column(Float, nullable=True)
    close_reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)


class ThemeHolding(Base):
    """A per-allocation lot — the theme book, kept SEPARATE from the discretionary
    account_positions so the trading engine never sees theme shares and each lot is
    attributable to one allocation. Paper-filled by the theme reconciler."""
    __tablename__ = "theme_holdings"
    __table_args__ = (
        UniqueConstraint("allocation_id", "symbol", name="uq_theme_holding"),
        Index("ix_theme_holdings_alloc", "allocation_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    allocation_id = Column(UUID(as_uuid=True), ForeignKey("theme_allocations.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)
    avg_cost = Column(Float, nullable=False, default=0.0)
    last_price = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ThemeEvent(Base):
    """Append-only audit + the live user-facing feed for a theme (one stream, two
    consumers: the admin timeline and the addictive card's reasoning feed)."""
    __tablename__ = "theme_events"
    __table_args__ = (Index("ix_theme_events_theme", "theme_id", "created_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(20), nullable=False)   # originated|thesis_update|rebalance|earnings|news|weaken|break|exit
    summary = Column(Text, nullable=False, default="")
    detail = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ThemeFollow(Base):
    """A user following a theme without (necessarily) funding it — a watchlist + the
    follower-count social proof."""
    __tablename__ = "theme_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "theme_id", name="uq_theme_follow"),
        Index("ix_theme_follows_theme", "theme_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ThemeComment(Base):
    """A user comment on a theme (Polymarket-style discussion wall)."""
    __tablename__ = "theme_comments"
    __table_args__ = (Index("ix_theme_comments_theme", "theme_id", "created_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ThemeCommentLike(Base):
    """A like on a theme comment (one per user per comment)."""
    __tablename__ = "theme_comment_likes"
    __table_args__ = (UniqueConstraint("comment_id", "user_id", name="uq_theme_comment_like"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(UUID(as_uuid=True), ForeignKey("theme_comments.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)



class Admin(Base):
    """A dedicated admin account (separate from user accounts) — for compliance,
    audit, and the central opportunity directory. New admins sign up as pending
    and are approved by an existing active admin. One root admin is seeded."""
    __tablename__ = "admins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False, default="")
    password_hash = Column(String(255), nullable=False)
    status = Column(String(12), nullable=False, default="pending")       # pending | active | rejected
    is_root = Column(Boolean, nullable=False, default=False)
    approved_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)


class TrackItem(Base):
    """A stock the user asked to WATCH (not auto-trade), max 3/user. Checked daily
    on math (price vs conservative FV → margin); when it enters an interesting
    range the harness does a deep dive and proposes it for the user's approval —
    tracking is watch-only until then."""
    __tablename__ = "track_items"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_track_user_symbol"),
        Index("ix_track_items_user", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    status = Column(String(16), nullable=False, default="watching")  # watching | interesting | proposed | archived
    last_check_at = Column(DateTime, nullable=True)
    last_price = Column(Float, nullable=True)
    last_margin_pct = Column(Float, nullable=True)
    note = Column(Text, nullable=True)                               # latest deep-dive summary
    order_id = Column(UUID(as_uuid=True), nullable=True)             # the proposal awaiting approval, if any
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserAgreement(Base):
    """A user's accept/reject of a versioned agreement — e.g. the live-trading
    T&C granting auto-approval for orders under the per-order cap. Keeps the full
    audit: doc, version, user, time, and accepted/rejected."""
    __tablename__ = "user_agreements"
    __table_args__ = (Index("ix_user_agreements_user_doc", "user_id", "doc"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    doc = Column(String(40), nullable=False)        # e.g. "live_trading"
    version = Column(String(16), nullable=False)    # e.g. "1.0"
    status = Column(String(10), nullable=False)     # "accepted" | "rejected"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BuyRule(Base):
    __tablename__ = "buy_rules"
    __table_args__ = (
        Index("ix_buy_rules_user", "user_id"),
        Index("ix_buy_rules_active", "is_active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(10), nullable=False)
    drop_pct = Column(Float, nullable=False)  # e.g. 10.0 = "10% below avg cost"
    market_benchmark = Column(String(10), nullable=False, default="QQQ")
    market_drop_pct = Column(Float, nullable=False)  # e.g. 5.0 = "QQQ down 5%+"
    max_excess_drop_pct = Column(Float, nullable=False, default=15.0)  # stock can't drop 15%+ MORE than market
    buy_amount_usd = Column(Float, nullable=False, default=500.0)
    is_active = Column(Boolean, default=True, nullable=False)
    check_interval_hours = Column(Integer, default=48, nullable=False)
    last_checked_at = Column(DateTime, nullable=True)
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="buy_rules")
    executions = relationship("Execution", back_populates="rule", lazy="noload")


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (
        Index("ix_executions_user", "user_id"),
        Index("ix_executions_rule", "rule_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("buy_rules.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(10), nullable=False)
    trigger_price = Column(Float, nullable=False)
    avg_cost = Column(Float, nullable=False)
    market_benchmark_price = Column(Float, nullable=False)
    market_drop_pct_actual = Column(Float, nullable=False)
    stock_drop_pct_actual = Column(Float, nullable=False)
    buy_amount_usd = Column(Float, nullable=False)
    shares_bought = Column(Float, nullable=True)
    order_id = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending | executed | failed | dry_run
    error_message = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    rule = relationship("BuyRule", back_populates="executions")
    user = relationship("User", back_populates="executions")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user", "user_id"),
        Index("ix_notifications_unread", "user_id", "is_read"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False)  # rule_triggered | order_executed | order_failed | rule_check | system
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("buy_rules.id"), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="notifications")


class Watchlist(Base):
    """User's persistent watchlist — DB-backed, not localStorage."""

    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),
        Index("ix_watchlist_user", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(10), nullable=False)
    name = Column(String(200), nullable=False, default="")
    thesis = Column(Text, nullable=False, default="")
    fair_value = Column(JSONB, nullable=True)        # {bear, base, bull}
    last_price = Column(Float, nullable=True)
    last_analyzed_at = Column(DateTime, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # background-populated on add: {metrics: {...FMP fundamentals...}, news: [...30d...], populated_at}
    meta = Column(JSONB, nullable=True)

    user = relationship("User")


class StockScore(Base):
    """Weekly stock validity score — tracks whether investment thesis still holds."""

    __tablename__ = "stock_scores"
    __table_args__ = (
        Index("ix_stock_scores_user_symbol", "user_id", "symbol"),
        Index("ix_stock_scores_scored_at", "scored_at"),
        UniqueConstraint("user_id", "symbol", "week_label", name="uq_stock_scores_user_symbol_week"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(10), nullable=False)
    company_name = Column(String(200), nullable=False, default="")

    # Composite validity score (0-100)
    validity_score = Column(Integer, nullable=False)

    # Sub-scores (each 0-100)
    fundamental_score = Column(Integer, nullable=False)  # margins, growth, cash flow quality
    valuation_score = Column(Integer, nullable=False)     # P/E vs historical, vs peers, DCF
    thesis_score = Column(Integer, nullable=False)        # are original drivers intact?
    momentum_score = Column(Integer, nullable=False)      # price action, analyst revisions

    # Verdict and detail
    verdict = Column(String(20), nullable=False)  # strong_buy | hold | watch | trim | sell
    thesis_summary = Column(Text, nullable=False, default="")
    concerns = Column(Text, nullable=False, default="")
    key_changes = Column(Text, nullable=False, default="")  # what changed since last score

    # Structured data for drilldown
    score_details = Column(JSONB, nullable=True)  # full scoring breakdown

    # Time tracking
    week_label = Column(String(10), nullable=False)  # e.g. "2026-W11"
    scored_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class StockMetrics(Base):
    """Shared stock metrics cache with per-field TTL timestamps."""

    __tablename__ = "stock_metrics"
    __table_args__ = (
        UniqueConstraint("ticker", name="uq_stock_metrics_ticker"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(10), nullable=False, index=True)

    # Market data (yfinance) — TTL: 15 min
    market_data = Column(JSONB, nullable=True)
    market_data_at = Column(DateTime, nullable=True)

    # Company info (yfinance) — TTL: 24h
    company_info = Column(JSONB, nullable=True)
    company_info_at = Column(DateTime, nullable=True)

    # Earnings (yfinance) — TTL: 7 days
    earnings = Column(JSONB, nullable=True)
    earnings_at = Column(DateTime, nullable=True)

    # News (yfinance) — TTL: 1h
    news = Column(JSONB, nullable=True)
    news_at = Column(DateTime, nullable=True)

    # AI Analysis (Claude) — TTL: 24h
    ai_analysis = Column(JSONB, nullable=True)
    ai_analysis_at = Column(DateTime, nullable=True)

    # AI Bear Case (Claude) — TTL: 24h
    ai_bear_case = Column(JSONB, nullable=True)
    ai_bear_case_at = Column(DateTime, nullable=True)

    # AI Sentiment (Claude) — TTL: 6h
    ai_sentiment = Column(JSONB, nullable=True)
    ai_sentiment_at = Column(DateTime, nullable=True)

    # Metadata
    access_count = Column(Integer, default=0, nullable=False)
    last_accessed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ApiUsage(Base):
    """Track per-user daily API usage for rate limiting free-tier (server-key) access."""

    __tablename__ = "api_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint_type", "usage_date", name="uq_api_usage_user_type_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    endpoint_type = Column(String(30), nullable=False)  # "analysis" | "advisor" | "brief"
    usage_date = Column(String(10), nullable=False)       # "2026-03-17"
    count = Column(Integer, default=0, nullable=False)


class DemoUsage(Base):
    """Track per-email daily API usage for rate limiting demo (unauthenticated) access."""

    __tablename__ = "demo_usage"
    __table_args__ = (
        UniqueConstraint("email", "endpoint_type", "usage_date", name="uq_demo_usage_email_type_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    endpoint_type = Column(String(30), nullable=False)  # "analysis" | "advisor" | "brief"
    usage_date = Column(String(10), nullable=False)       # "2026-03-21"
    count = Column(Integer, default=0, nullable=False)


class WaitlistEmail(Base):
    """Email waitlist signups from the landing page."""

    __tablename__ = "waitlist_emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="landing")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StressTestResultDB(Base):
    """Persisted stress test results for caching and history."""

    __tablename__ = "stress_test_results"
    __table_args__ = (
        Index("ix_stress_results_cache_key", "cache_key"),
        Index("ix_stress_results_expires", "expires_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cache_key = Column(String(64), unique=True, nullable=False)
    scenario_id = Column(String(100), nullable=False)
    scenario_version = Column(String(20), nullable=False)
    custom_input = Column(Text, nullable=True)
    result_data = Column(JSONB, nullable=False)
    portfolio_hash = Column(String(64), nullable=False)
    portfolio_size = Column(Integer, nullable=False)
    methodology = Column(String(30), nullable=False)
    confidence_level = Column(String(10), nullable=False)
    computation_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class AdvisorSession(Base):
    """A saved Advisor conversation (session history) per user. Messages are
    stored inline as a JSON array; the account the portfolio context was drawn
    from is pinned to the session."""

    __tablename__ = "advisor_sessions"
    __table_args__ = (
        Index("ix_advisor_sessions_user", "user_id", "updated_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account = Column(String(40), nullable=True)              # account number used for context
    title = Column(String(200), nullable=False, default="New chat")
    messages = Column(JSONB, nullable=False, default=list)   # [{role, content, timestamp}]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User")


# ── Agentic Trading ("The Partner") ──────────────────────────────────
# Robinhood is the source of truth for positions (refreshed at cadence); these
# tables are the source of truth for what the agent DID — an immutable audit trail.

class AgentMandate(Base):
    """The user's Mandate for one agentic account: autonomy limits + cadence +
    strategy. One row per (user, account). The hard caps the SafetyGate enforces."""

    __tablename__ = "agent_mandates"
    __table_args__ = (UniqueConstraint("user_id", "account", name="uq_agent_mandate_user_account"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account = Column(String(40), nullable=False)                 # the AGENTIC account number
    # autonomy + hard caps
    approval_threshold_usd = Column(Float, nullable=False, default=25_000.0)
    per_trade_cap_usd = Column(Float, nullable=False, default=50_000.0)
    daily_spend_cap_usd = Column(Float, nullable=False, default=50_000.0)
    max_position_pct = Column(Float, nullable=False, default=0.09)   # weight ceiling
    cash_floor_pct = Column(Float, nullable=False, default=0.10)
    sector_cap_pct = Column(Float, nullable=False, default=0.30)
    max_orders_week = Column(Integer, nullable=False, default=3)
    # Catastrophic-drawdown REVIEW threshold (fraction, e.g. 0.30 = −30% from cost).
    # NOT a stop-loss: a wide backstop that forces a thesis re-review → propose exit
    # only if the thesis can't be reaffirmed (never a silent auto-sell). NULL = platform
    # default (CATASTROPHIC_DD_DEFAULT); 0 or negative disables the backstop.
    catastrophic_stop_pct = Column(Float, nullable=True)
    cadence = Column(String(8), nullable=False, default="1h")        # 5m|15m|30m|1h|Daily (1h is the default)
    # execution target: which account the agent trades — the paper↔live toggle.
    #   paper   → the user's paper account (simulated)
    #   live    → the fenced Robinhood agentic account (REAL money)
    #   dry_run → decide + record only, place nothing (free stub brain)
    mode = Column(String(10), nullable=False, default="paper")
    live_max_notional_usd = Column(Float, nullable=False, default=100.0)  # "small cap" ceiling per live order
    margin_of_safety_pct = Column(Float, nullable=False, default=30.0)    # required discount to conservative fair value before buying
    # circle of competence — sectors the agent may/mustn't act in (empty include = any)
    circle_include = Column(JSONB, nullable=False, default=list)
    circle_exclude = Column(JSONB, nullable=False, default=list)
    # strategy (the StrategySpec, inline for now)
    strategy_name = Column(String(80), nullable=False, default="Munger — patient quality")
    strategy_objective = Column(Text, nullable=False, default="Compound steadily; buy rarely at a margin of safety; avoid permanent loss.")
    strategy_rules = Column(Text, nullable=False, default="")
    # control
    paused = Column(Boolean, nullable=False, default=False)
    toggles = Column(JSONB, nullable=False, default=dict)            # new_pos_approval, loss_sale_approval, earnings_days, after_hours, phone, queue, daily_push
    # scheduling
    next_tick_at = Column(DateTime, nullable=True)
    last_tick_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User")


class AgentOrder(Base):
    """The trade audit log — every order the agent proposes, and its lifecycle.
    Append + status transitions; never deleted. `dry_run` orders are proposals the
    agent WOULD have placed (P1)."""

    __tablename__ = "agent_orders"
    __table_args__ = (
        Index("ix_agent_orders_user", "user_id", "created_at"),
        Index("ix_agent_orders_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account = Column(String(40), nullable=False)
    tick_id = Column(UUID(as_uuid=True), ForeignKey("agent_ticks.id"), nullable=True)
    screen_id = Column(UUID(as_uuid=True), nullable=True)
    symbol = Column(String(10), nullable=False)
    side = Column(String(4), nullable=False)                     # buy | sell
    qty = Column(Float, nullable=False)
    order_type = Column(String(8), nullable=False, default="market")
    limit_price = Column(Float, nullable=True)
    est_price = Column(Float, nullable=False, default=0.0)
    est_notional = Column(Float, nullable=False, default=0.0)
    rationale = Column(Text, nullable=False, default="")
    confidence = Column(Float, nullable=False, default=0.0)
    # lifecycle: proposed|pending_approval|approved|declined|placed|filled|rejected|failed|expired
    status = Column(String(20), nullable=False, default="proposed")
    approval_required = Column(Boolean, nullable=False, default=False)
    approved_at = Column(DateTime, nullable=True)
    declined_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    # execution (P2+)
    robinhood_order_id = Column(String(64), nullable=True)
    fill_price = Column(Float, nullable=True)
    filled_qty = Column(Float, nullable=True)
    filled_notional = Column(Float, nullable=True)
    client_order_id = Column(String(64), nullable=True, index=True)  # idempotency
    error_message = Column(Text, nullable=True)
    dry_run = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User")


class AgentTick(Base):
    """One review/wake of the agent — including non-actions ('checked, did nothing').
    Stores the positions snapshot the agent saw (audit + net-liquidity history)."""

    __tablename__ = "agent_ticks"
    __table_args__ = (Index("ix_agent_ticks_user", "user_id", "created_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account = Column(String(40), nullable=False)
    reason = Column(String(16), nullable=False, default="cadence")   # cadence|manual|earnings
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    snapshot = Column(JSONB, nullable=True)                          # positions + cash + equity at tick time
    decision_action = Column(String(4), nullable=False, default="hold")
    decision_rationale = Column(Text, nullable=False, default="")
    confidence = Column(Float, nullable=False, default=0.0)
    gate_status = Column(String(16), nullable=False, default="noop")  # executed|pending_approval|rejected|noop
    order_id = Column(UUID(as_uuid=True), nullable=True)
    screen_id = Column(UUID(as_uuid=True), nullable=True)
    model = Column(String(40), nullable=True)
    usage = Column(JSONB, nullable=True)
    dry_run = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class AgentLedgerEntry(Base):
    """The feed the UI renders — one row per audit-worthy event (check, screen,
    pass, executed, awaiting, approved, declined, error, note)."""

    __tablename__ = "agent_ledger"
    __table_args__ = (Index("ix_agent_ledger_user", "user_id", "ts"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account = Column(String(40), nullable=False)
    tick_id = Column(UUID(as_uuid=True), nullable=True)
    order_id = Column(UUID(as_uuid=True), nullable=True)
    screen_id = Column(UUID(as_uuid=True), nullable=True)
    type = Column(String(16), nullable=False)                       # check|screen|pass|executed|awaiting|approved|declined|error|note
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    title = Column(String(240), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    meta = Column(JSONB, nullable=True)                             # badge, order line, quote, links, funnel numbers
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class AgentScreen(Base):
    """The elimination funnel for a morning screen (214→12→4→1) with per-ticker
    kill reasons — powers the screen-detail drill-in."""

    __tablename__ = "agent_screens"
    __table_args__ = (Index("ix_agent_screens_user", "user_id", "created_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account = Column(String(40), nullable=False)
    tick_id = Column(UUID(as_uuid=True), nullable=True)
    universe_count = Column(Integer, nullable=False, default=0)
    stages = Column(JSONB, nullable=False, default=list)            # [{count, label, tickers, exclusions}]
    survivor = Column(String(10), nullable=True)
    verdict = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class AgentPrinciple(Base):
    """The Latticework — principles that govern the agent. Seeded per user with the
    Munger core set; editable (P3). Nothing applies until a backtest passes."""

    __tablename__ = "agent_principles"
    __table_args__ = (Index("ix_agent_principles_user", "user_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    section = Column(String(24), nullable=False)                    # Temperament|Selection|Sizing & Selling
    text = Column(Text, nullable=False)
    meta = Column(Text, nullable=False, default="")
    source = Column(String(12), nullable=False, default="core")     # core|munger|research|yours
    paused = Column(Boolean, nullable=False, default=False)
    order_idx = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User")


class PortfolioBrief(Base):
    """Cached deep portfolio analysis (the 'Portfolio Analysis' / Daily Brief —
    deep research on every holding) per user & account. Served unchanged across
    sessions/devices until the user explicitly refreshes (regenerates)."""

    __tablename__ = "portfolio_briefs"
    __table_args__ = (
        UniqueConstraint("user_id", "account", name="uq_portfolio_briefs_user_account"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account = Column(String(40), nullable=False, default="default")
    data = Column(JSONB, nullable=False)            # the full analysis payload
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StockSensitivityProfile(Base):
    """Cached stock sensitivity data for stress test calculations.

    Stores beta, sector, quality score, factor exposures, and geographic
    revenue breakdown. Refreshed daily by background job.
    """

    __tablename__ = "stock_sensitivity_profiles"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_stock_sensitivity_symbol"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(10), nullable=False, index=True)
    sector = Column(String(100), nullable=False, default="Unknown")
    industry = Column(String(200), nullable=False, default="Unknown")
    size_tier = Column(String(20), nullable=False, default="Unknown")
    primary_region = Column(String(30), nullable=False, default="Unknown")
    beta = Column(Float, nullable=True)
    quality_score = Column(Integer, nullable=True)
    fundamentals = Column(JSONB, nullable=True)
    factor_exposures = Column(JSONB, nullable=True)
    revenue_exposure = Column(JSONB, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AgentMemory(Base):
    """Per-account LONG-TERM memory — a compact, curated knowledge doc (holdings
    history, lessons, per-name knowledge, standing context). Rewritten weekly by the
    'librarian' compaction; read into every tick so the agent acts with continuity."""

    __tablename__ = "agent_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account = Column(String(40), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    long_term = Column(Text, nullable=True)                         # compact consolidated memory (markdown)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AgentMemoryDay(Base):
    """Per-account SHORT-TERM memory — one compact deterministic summary per day
    (built from the ledger). Kept for the current week, then folded into long_term
    by the Sunday compaction and pruned."""

    __tablename__ = "agent_memory_day"
    __table_args__ = (UniqueConstraint("account", "day", name="uq_agent_memory_day"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account = Column(String(40), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    day = Column(Date, nullable=False)
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CommunityPost(Base):
    """One public community channel — a chat `message` or a shared `pnl_card`
    (Spotify-Wrapped-style P&L snapshot). Read is public; posting requires sign-in.
    New table → auto-created by Base.metadata.create_all on startup (no migration)."""

    __tablename__ = "community_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Denormalized author display so the feed needs no join and survives handle changes.
    author_name = Column(String(100), nullable=False)
    author_handle = Column(String(50), nullable=True)      # public_id or username
    kind = Column(String(16), nullable=False, default="message")   # "message" | "pnl_card"
    body = Column(Text, nullable=True)                     # chat text, or caption on a card
    stats = Column(JSONB, nullable=True)                   # pnl_card snapshot {portfolioValue, totalReturnPct, …}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
