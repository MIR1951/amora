"""staff, invites, delay alerts, daily report

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17 00:20:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staff",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("added_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_table(
        "staff_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_by", sa.BigInteger(), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.add_column("orders", sa.Column("customer_order_no", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("alerted_status", sa.String(length=20), nullable=True))
    op.add_column(
        "shop_settings",
        sa.Column("alert_accept_minutes", sa.Integer(), server_default="5", nullable=False),
    )
    op.add_column(
        "shop_settings",
        sa.Column("alert_delivery_minutes", sa.Integer(), server_default="45", nullable=False),
    )
    op.add_column(
        "shop_settings",
        sa.Column("daily_report_to", sa.String(length=10), server_default="group", nullable=False),
    )
    op.add_column(
        "shop_settings",
        sa.Column("daily_report_sent_until", sa.DateTime(timezone=True), nullable=True),
    )
    # Mavjud buyurtmalar kechikish eslatmasini qayta olmasin: yangilanishdan oldingilarini belgilaymiz
    op.execute("UPDATE orders SET alerted_status = status")
    op.create_index("ix_orders_phone", "orders", ["phone"])


def downgrade() -> None:
    op.drop_index("ix_orders_phone", table_name="orders")
    op.drop_column("shop_settings", "daily_report_sent_until")
    op.drop_column("shop_settings", "daily_report_to")
    op.drop_column("shop_settings", "alert_delivery_minutes")
    op.drop_column("shop_settings", "alert_accept_minutes")
    op.drop_column("orders", "alerted_status")
    op.drop_column("orders", "customer_order_no")
    op.drop_table("staff_invites")
    op.drop_table("staff")
