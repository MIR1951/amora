"""phone verification through Telegram, several devices per customer

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-17 09:30:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("fcm_token", sa.String(length=255), nullable=True),
        sa.Column("platform", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_customer_devices_customer_id", "customer_devices", ["customer_id"])
    # Hozirgi har bir mijoz = bitta qurilma: kirish kalitlari va push manzillari ko'chiriladi
    op.execute(
        "INSERT INTO customer_devices (customer_id, token_hash, fcm_token, platform, created_at) "
        "SELECT id, token_hash, fcm_token, platform, created_at FROM customers"
    )
    op.drop_constraint("customers_token_hash_key", "customers", type_="unique")
    op.drop_column("customers", "token_hash")
    op.drop_column("customers", "fcm_token")
    op.drop_column("customers", "platform")
    op.add_column(
        "customers",
        sa.Column("phone_verified", sa.Boolean(), server_default="0", nullable=False),
    )
    op.add_column("customers", sa.Column("telegram_user_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_customers_telegram_user_id", "customers", ["telegram_user_id"])

    op.create_table(
        "phone_verifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=60), nullable=True),
        sa.Column("platform", sa.String(length=10), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_name", sa.String(length=60), nullable=True),
        sa.Column("phone", sa.String(length=13), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["customer_devices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(
        "ix_phone_verifications_telegram_user_id", "phone_verifications", ["telegram_user_id"]
    )
    op.add_column("orders", sa.Column("customer_telegram_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "customer_telegram_id")
    op.drop_index("ix_phone_verifications_telegram_user_id", table_name="phone_verifications")
    op.drop_table("phone_verifications")
    op.drop_index("ix_customers_telegram_user_id", table_name="customers")
    op.drop_column("customers", "telegram_user_id")
    op.drop_column("customers", "phone_verified")
    op.add_column("customers", sa.Column("platform", sa.String(length=10), nullable=True))
    op.add_column("customers", sa.Column("fcm_token", sa.String(length=255), nullable=True))
    op.add_column("customers", sa.Column("token_hash", sa.String(length=64), nullable=True))
    # Har bir mijozning oxirgi qurilmasi qaytariladi, qolganlari chiqib ketadi
    op.execute(
        "UPDATE customers SET token_hash = d.token_hash, fcm_token = d.fcm_token, "
        "platform = d.platform FROM ("
        "  SELECT DISTINCT ON (customer_id) customer_id, token_hash, fcm_token, platform "
        "  FROM customer_devices ORDER BY customer_id, id DESC"
        ") AS d WHERE d.customer_id = customers.id"
    )
    op.execute("DELETE FROM customers WHERE token_hash IS NULL AND id NOT IN (SELECT customer_id FROM orders)")
    op.execute("UPDATE customers SET token_hash = md5(random()::text) || md5(random()::text) WHERE token_hash IS NULL")
    op.alter_column("customers", "token_hash", nullable=False)
    op.create_unique_constraint("customers_token_hash_key", "customers", ["token_hash"])
    op.drop_index("ix_customer_devices_customer_id", table_name="customer_devices")
    op.drop_table("customer_devices")
