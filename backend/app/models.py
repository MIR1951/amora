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
        Index("ix_orders_phone", "phone"),
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
    # Promokod yoki birinchi buyurtma aksiyasi bo'yicha chegirma (faqat taomlarga)
    discount: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    promo_id: Mapped[int | None] = mapped_column(
        ForeignKey("promo_codes.id", ondelete="SET NULL"), nullable=True
    )
    promo_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    total: Mapped[int] = mapped_column(Integer)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Guruhdagi xabar: bot uni holat o'zgarganda tahrirlaydi
    tg_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Shu raqamdan berilgan nechanchi buyurtma (1 = yangi mijoz). Eski buyurtmalarda bo'sh
    customer_order_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Kechikish haqida qaysi holat uchun guruhga eslatma yuborilgan: har holatga bir marta
    alerted_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

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

    # Kechikish eslatmasi: buyurtma shuncha daqiqa qabul qilinmasa yoki yo'lda tursa (0 = o'chiq)
    alert_accept_minutes: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    alert_delivery_minutes: Mapped[int] = mapped_column(Integer, default=45, server_default="45")
    # Kunlik hisobot kafe yopilganda qayerga yuboriladi: group | admins | off
    daily_report_to: Mapped[str] = mapped_column(String(10), default="group", server_default="group")
    # Oxirgi yuborilgan kunlik hisobot qaysi ish kuni oxiriga tegishli (ikki marta ketmasligi uchun)
    daily_report_sent_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    # Ilovadagi bosh sahifa banneri. Bo'sh bo'lsa ilova yetkazish shartlarini ko'rsatadi
    banner_title: Mapped[str | None] = mapped_column(String(40), nullable=True)
    banner_text: Mapped[str | None] = mapped_column(String(80), nullable=True)


class PromoKind(StrEnum):
    PERCENT = "percent"  # foiz
    AMOUNT = "amount"  # aniq summa (so'm)


class PromoCode(Base):
    """Promokod yoki (is_auto) kod kiritmasdan beriladigan birinchi buyurtma chegirmasi."""

    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    is_auto: Mapped[bool] = mapped_column(Boolean, default=False)
    kind: Mapped[str] = mapped_column(String(10))
    value: Mapped[int] = mapped_column(Integer)
    max_discount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_order: Mapped[int] = mapped_column(Integer, default=0)
    first_order_only: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    def discount_for(self, items_total: int) -> int:
        if self.kind == PromoKind.PERCENT.value:
            amount = items_total * self.value // 100
            if self.max_discount:
                amount = min(amount, self.max_discount)
        else:
            amount = self.value
        return max(0, min(amount, items_total))


class StaffRole(StrEnum):
    ADMIN = "admin"  # hamma narsa: menyu, sozlamalar, xodimlar
    STAFF = "staff"  # taom bor/tugadi, qabulni to'xtatish, hisobot, mijoz kartasi


class Staff(Base):
    """Botdan qo'shilgan admin va xodimlar. Egasi (AMORA_ADMIN_IDS) bu jadvalda bo'lmaydi."""

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(10))
    added_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class StaffInvite(Base):
    """Bir martalik taklif havolasi: t.me/<bot>?start=inv_<token>."""

    __tablename__ = "staff_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(32), unique=True)
    role: Mapped[str] = mapped_column(String(10))
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
