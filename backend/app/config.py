"""Sozlamalar. Hammasi AMORA_ prefiksli muhit o'zgaruvchilaridan yoki .env fayldan o'qiladi."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AMORA_", extra="ignore")

    database_url: str = "postgresql+asyncpg://amora:amora@localhost:5432/amora"

    # Rasmlar manzili shu asosda tuziladi, masalan https://api.amora.uz
    public_base_url: str = "http://localhost:8000"
    media_dir: Path = Path("media")

    # Ish vaqti shu vaqt mintaqasida hisoblanadi
    timezone: str = "Asia/Tashkent"

    # Telegram (2-bosqichda ishlatiladi)
    bot_token: str = ""
    # Raqamni tasdiqlash havolasi uchun (masalan amora_kafebot). Yozilmasa, bot tokeni orqali olinadi
    bot_username: str = ""
    orders_chat_id: int | None = None
    admin_ids: str = ""  # vergul bilan ajratilgan Telegram user id'lar

    # Soxta buyurtmalardan himoya
    max_active_orders: int = 2
    # Bitta mijoz soatiga ko'pi bilan nechta buyurtma bera oladi (bekor qilinganlari ham). 0 = cheklovsiz
    max_orders_per_hour: int = 8
    register_limit_per_hour: int = 10
    # Do'kon (App Store / Google Play) tekshiruvchisi uchun sinov kodi. Tekshiruvchi uni "Ism"
    # maydoniga yozib, tasdiqlashni bosadi: Telegram'siz sinov hisobiga kiradi. Bo'sh = o'chiq.
    # Kamida 12 belgi bo'lsin; tekshiruv tugagach o'chirib qo'ying. Sinov buyurtmalari guruhga
    # "SINOV BUYURTMA" belgisi bilan tushadi
    review_code: str = ""
    # Bitta IP manzildan soatiga nechta tasdiqlash so'rovi (mobil internetda ko'p odam bitta IP'da)
    verify_limit_per_hour: int = 30

    # Firebase service account kaliti (JSON). Yozilmasa push-bildirishnomalar o'chiq
    firebase_credentials: Path | None = None
    # iPhone push (APNs): .p8 kalit fayli, Key ID, Team ID. Yozilmasa iPhone'ga push o'chiq
    apns_key: Path | None = None
    apns_key_id: str = ""
    apns_team_id: str = ""
    apns_topic: str = "uz.amora.app"
    # Faqat Xcode'dan o'rnatilgan sinov ilovalari uchun true (TestFlight/App Store: false)
    apns_sandbox: bool = False

    # Eski ilovalar uchun raqamni tekshirmasdan ro'yxatdan o'tish (/auth/register). Bunday hisob
    # buyurtma bera olmaydi. Hozirgi ilovalar buni ishlatmaydi, shuning uchun standart holatda o'chiq
    allow_legacy_register: bool = False

    debug: bool = False

    @field_validator("public_base_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("firebase_credentials", "apns_key", mode="before")
    @classmethod
    def _empty_path_to_none(cls, value):
        return None if value == "" else value

    @field_validator("orders_chat_id", mode="before")
    @classmethod
    def _empty_to_none(cls, value):
        return None if value == "" else value

    @property
    def admin_id_set(self) -> set[int]:
        return {int(part) for part in self.admin_ids.replace(" ", "").split(",") if part}


@lru_cache
def get_settings() -> Settings:
    return Settings()
