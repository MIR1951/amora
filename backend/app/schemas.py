from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security import normalize_phone

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


def _clean(value: str) -> str:
    return " ".join(value.split())


# ---------- Menyu va kafe ----------


class CategoryOut(BaseModel):
    id: int
    name: str


class ProductOut(BaseModel):
    id: int
    category_id: int | None
    name: str
    description: str
    price: int
    image_url: str | None
    is_available: bool


class MenuOut(BaseModel):
    categories: list[CategoryOut]
    products: list[ProductOut]


class ShopOut(BaseModel):
    cafe_name: str
    phone: str | None
    is_open: bool
    is_accepting_orders: bool
    open_time: str
    close_time: str
    delivery_fee: int
    free_delivery_from: int | None
    min_order_amount: int
    max_delivery_km: float | None
    cafe_latitude: float | None
    cafe_longitude: float | None
    banner_title: str | None = None
    banner_text: str | None = None


# ---------- Mijoz ----------


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    phone: str
    platform: Literal["android", "ios"] | None = None

    _clean_name = field_validator("name")(_clean)
    _normalize_phone = field_validator("phone")(normalize_phone)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("Ismingizni kiriting")
        return value


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str


class RegisterOut(BaseModel):
    token: str
    customer: CustomerOut


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    phone: str | None = None
    fcm_token: str | None = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = _clean(value)
        if not value:
            raise ValueError("Ismingizni kiriting")
        return value

    @field_validator("phone")
    @classmethod
    def _normalize(cls, value: str | None) -> str | None:
        return None if value is None else normalize_phone(value)


# ---------- Savat va buyurtma ----------


class CartItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=50)


class QuoteIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1, max_length=30)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    promo_code: str | None = Field(default=None, max_length=30)
    # Yangi ilova shuni yuboradi: birinchi buyurtma chegirmasi kod kiritmasdan qo'llanadi.
    # Eski ilovalarda summa kutilmaganda o'zgarib qolmasligi uchun standart holatda o'chiq
    apply_auto_promo: bool = False
    # Ilova bilgan telefon (mijoz hali ro'yxatdan o'tmagan bo'lsa): birinchi buyurtma
    # chegirmasi shu raqam bo'yicha tekshiriladi. Token yuborilsa, tokendagi raqam ustun
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("phone")
    @classmethod
    def _normalize_quote_phone(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return normalize_phone(value)
        except ValueError:
            return None  # noto'g'ri raqam savat hisobiga xalaqit bermaydi


class ProblemOut(BaseModel):
    code: str
    message: str
    product_id: int | None = None


class QuoteLineOut(BaseModel):
    product_id: int
    name: str
    price: int
    quantity: int
    line_total: int


class QuoteOut(BaseModel):
    lines: list[QuoteLineOut]
    items_total: int
    delivery_fee: int
    total: int
    distance_km: float | None
    can_order: bool
    problems: list[ProblemOut]
    discount: int = 0
    promo_title: str | None = None  # "AMORA10: −10%" yoki "Birinchi buyurtma: −15%"
    promo_error: str | None = None  # kiritilgan kod ishlamadi: sababi


class OrderIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1, max_length=30)
    latitude: Latitude
    longitude: Longitude
    address_note: str = Field(default="", max_length=255)
    comment: str = Field(default="", max_length=500)
    # Bo'sh bo'lsa mijoz profilidagi ism va raqam olinadi
    name: str | None = Field(default=None, max_length=60)
    phone: str | None = None
    # Ilova har bir buyurtma uchun yaratadigan UUID: qayta yuborilganda ikkilanmaydi
    client_order_id: UUID | None = None
    # Ilova ko'rsatgan jami summa: narx o'zgargan bo'lsa server buyurtmani qabul qilmaydi
    expected_total: int | None = Field(default=None, ge=0)
    promo_code: str | None = Field(default=None, max_length=30)
    apply_auto_promo: bool = False

    _clean_note = field_validator("address_note", "comment")(_clean)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        return (_clean(value) or None) if value is not None else None

    @field_validator("phone")
    @classmethod
    def _normalize(cls, value: str | None) -> str | None:
        return None if value is None else normalize_phone(value)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int | None
    name: str
    price: int
    quantity: int
    line_total: int


class StatusEventOut(BaseModel):
    status: str
    status_label: str
    created_at: datetime


class OrderOut(BaseModel):
    id: int
    status: str
    status_label: str
    is_active: bool
    can_cancel: bool
    items: list[OrderItemOut]
    items_total: int
    delivery_fee: int
    discount: int = 0
    promo_code: str | None = None
    total: int
    customer_name: str
    phone: str
    latitude: float
    longitude: float
    address_note: str
    comment: str
    reject_reason: str | None
    created_at: datetime
    updated_at: datetime
    history: list[StatusEventOut]


class OrderListOut(BaseModel):
    orders: list[OrderOut]
    has_more: bool
