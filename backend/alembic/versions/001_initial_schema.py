"""Initial schema — users, buy_rules, executions, notifications + test account

Revision ID: 001
Revises: None
Create Date: 2026-02-25
"""
from typing import Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None

# Pre-generated UUID for the test account so it's deterministic
TEST_USER_ID = uuid.UUID("00000000-0000-4000-a000-000000000001")


def upgrade() -> None:
    # ── Users ────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("robinhood_connected", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── Buy Rules ────────────────────────────────────────
    op.create_table(
        "buy_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("drop_pct", sa.Float, nullable=False),
        sa.Column("market_benchmark", sa.String(10), nullable=False, server_default="QQQ"),
        sa.Column("market_drop_pct", sa.Float, nullable=False),
        sa.Column("max_excess_drop_pct", sa.Float, nullable=False, server_default="15.0"),
        sa.Column("buy_amount_usd", sa.Float, nullable=False, server_default="500.0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("check_interval_hours", sa.Integer, nullable=False, server_default="48"),
        sa.Column("last_checked_at", sa.DateTime, nullable=True),
        sa.Column("last_triggered_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_buy_rules_user", "buy_rules", ["user_id"])
    op.create_index("ix_buy_rules_active", "buy_rules", ["is_active"])

    # ── Executions ───────────────────────────────────────
    op.create_table(
        "executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("buy_rules.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("trigger_price", sa.Float, nullable=False),
        sa.Column("avg_cost", sa.Float, nullable=False),
        sa.Column("market_benchmark_price", sa.Float, nullable=False),
        sa.Column("market_drop_pct_actual", sa.Float, nullable=False),
        sa.Column("stock_drop_pct_actual", sa.Float, nullable=False),
        sa.Column("buy_amount_usd", sa.Float, nullable=False),
        sa.Column("shares_bought", sa.Float, nullable=True),
        sa.Column("order_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("executed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_executions_user", "executions", ["user_id"])
    op.create_index("ix_executions_rule", "executions", ["rule_id"])

    # ── Notifications ────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("buy_rules.id"), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user", "notifications", ["user_id"])
    op.create_index("ix_notifications_unread", "notifications", ["user_id", "is_read"])

    # ── Seed: test account ───────────────────────────────
    # Password: test1234 → bcrypt hash
    # Generated via: bcrypt.hashpw(b"test1234", bcrypt.gensalt())
    op.execute(
        sa.text(
            """INSERT INTO users (id, username, password_hash, display_name)
               VALUES (:id, :username, :password_hash, :display_name)
               ON CONFLICT (username) DO NOTHING"""
        ).bindparams(
            id=TEST_USER_ID,
            username="konda",
            password_hash="$2b$12$0T/AT7z8696mOYyJmwY4BuE.utQF6uHXplIpz9mdmYf4chvefigN6",
            display_name="Konda Reddy",
        )
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("executions")
    op.drop_table("buy_rules")
    op.drop_table("users")
