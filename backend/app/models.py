from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime, utcnow


class OrderStatus(StrEnum):
    NEW = "new"  # mijoz yubordi, kafe hali javob bermadi
    ACCEPTED = "accepted"  # kafe qabul qildi, tayyorlanmoqda
    DELIVERING = "delivering"  # kuryer yo'lda
    DELIVERED = "delivered"
    REJECTED = "rejected"  # kafe rad etdi
    CANCELLED = "cancelled"  # mijoz bekor qildi


STATUS_LABELS: dict[OrderStatus, str] = {
    OrderStatus.NEW: "Kafe javobi kutilmoqda",
    OrderStatus.ACCEPTED: "Tayyorlanmoqda",
    OrderStatus.DELIVERING: "Kuryer yo'lda",
    OrderStatus.DELIVERED: "Yetkazildi",
    OrderStatus.REJECTED: "Rad etildi",
    OrderStatus.CANCELLED: "Bekor qilindi",
}

ACTIVE_STATUSES = (OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.DELIVERING)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer)  # so'mda
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Telegram file_id: bot rasmni qayta yuklamasdan ko'rsata olishi uchun
    image_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)  # tugab qolsa False
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    category: Mapped[Category | None] = relationship(back_populates="products")


class Customer(Base):
    """Bitta qurilmadagi mijoz.

    SMS tasdiqlash yo'q, shuning uchun telefon raqam egasini tekshira olmaymiz.
    Buyurtmalar tarixi raqamga emas, qurilmadagi tokenga bog'lanadi: birovning
    raqamini yozgan odam uning manzillarini ko'ra olmaydi.
    """

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    phone: Mapped[str] = mapped_column(String(13), index=True)  # +998XXXXXXXXX
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    fcm_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(10), nullable=True)  # android / ios
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("customer_id", "client_order_id", name="uq_orders_customer_client_id"),
        Index("ix_orders_customer_created", "customer_id", "created_at"),
        Index("ix_orders_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    # Ilova har bir buyurtmaga UUID beradi: internet uzilib qayta yuborilsa, ikkilanmaydi
    client_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.NEW.value)

    customer_name: Mapped[str] = mapped_column(String(60))
    phone: Mapped[str] = mapped_column(String(13))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    address_note: Mapped[str] = mapped_column(String(255), default="")  # uy, kvartira, mo'ljal
    comment: Mapped[str] = mapped_column(String(500), default="")

    items_total: Mapped[int] = mapped_column(Integer)
    delivery_fee: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Guruhdagi xabar: bot uni holat o'zgarganda tahrirlaydi
    tg_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    history: Mapped[list["OrderStatusEvent"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderStatusEvent.id"
    )

    @property
    def status_enum(self) -> OrderStatus:
        return OrderStatus(self.status)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    # Nom va narx buyurtma paytidagi holatda saqlanadi: menyu keyin o'zgarsa ham tarix buzilmaydi
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")

    @property
    def line_total(self) -> int:
        return self.price * self.quantity


class OrderStatusEvent(Base):
    __tablename__ = "order_status_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(100), default="")  # "mijoz" yoki xodim ismi
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    order: Mapped[Order] = relationship(back_populates="history")


class ShopSettings(Base):
    """Kafe sozlamalari. Jadvalda har doim bitta qator (id=1) bo'ladi."""

    __tablename__ = "shop_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cafe_name: Mapped[str] = mapped_column(String(60), default="Amora")
    phone: Mapped[str | None] = mapped_column(String(13), nullable=True)

    cafe_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    cafe_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    delivery_fee: Mapped[int] = mapped_column(Integer, default=0)
    free_delivery_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_order_amount: Mapped[int] = mapped_column(Integer, default=0)
    max_delivery_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    open_time: Mapped[time] = mapped_column(Time, default=time(9, 0))
    close_time: Mapped[time] = mapped_column(Time, default=time(23, 0))
    # Qo'lda o'chirish: kafe band bo'lsa yoki dam olish kuni
    is_accepting_orders: Mapped[bool] = mapped_column(Boolean, default=True)
