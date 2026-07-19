"""add stock_scores table

Revision ID: 002_add_stock_scores
Revises: 001_initial_schema
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_add_stock_scores"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("validity_score", sa.Integer(), nullable=False),
        sa.Column("fundamental_score", sa.Integer(), nullable=False),
        sa.Column("valuation_score", sa.Integer(), nullable=False),
        sa.Column("thesis_score", sa.Integer(), nullable=False),
        sa.Column("momentum_score", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("thesis_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("concerns", sa.Text(), nullable=False, server_default=""),
        sa.Column("key_changes", sa.Text(), nullable=False, server_default=""),
        sa.Column("score_details", postgresql.JSONB(), nullable=True),
        sa.Column("week_label", sa.String(10), nullable=False),
        sa.Column("scored_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stock_scores_user_symbol", "stock_scores", ["user_id", "symbol"])
    op.create_index("ix_stock_scores_scored_at", "stock_scores", ["scored_at"])
    op.create_unique_constraint(
        "uq_stock_scores_user_symbol_week", "stock_scores", ["user_id", "symbol", "week_label"]
    )


def downgrade() -> None:
    op.drop_table("stock_scores")
