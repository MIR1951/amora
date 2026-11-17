"""promo codes, order discount, home banner

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-17 01:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=True),
        sa.Column("is_auto", sa.Boolean(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("max_discount", sa.Integer(), nullable=True),
        sa.Column("min_order", sa.Integer(), nullable=False),
        sa.Column("first_order_only", sa.Boolean(), nullable=False),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.add_column("orders", sa.Column("discount", sa.Integer(), server_default="0", nullable=False))
    op.add_column("orders", sa.Column("promo_id", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("promo_code", sa.String(length=30), nullable=True))
    op.create_foreign_key(
        "orders_promo_id_fkey", "orders", "promo_codes", ["promo_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column("shop_settings", sa.Column("banner_title", sa.String(length=40), nullable=True))
    op.add_column("shop_settings", sa.Column("banner_text", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("shop_settings", "banner_text")
    op.drop_column("shop_settings", "banner_title")
    op.drop_constraint("orders_promo_id_fkey", "orders", type_="foreignkey")
    op.drop_column("orders", "promo_code")
    op.drop_column("orders", "promo_id")
    op.drop_column("orders", "discount")
    op.drop_table("promo_codes")
