"""Telegram'siz sinash: so'rovlar internetga chiqmaydi, ro'yxatga yozib boriladi."""

from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import (
    EditMessageReplyMarkup,
    EditMessageText,
    GetFile,
    GetMe,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    File,
    InlineKeyboardMarkup,
    Location,
    Message,
    PhotoSize,
    Update,
    User,
)

ADMIN_ID = 111
STRANGER_ID = 999
GROUP_ID = -1001234567890
STAFF = User(id=555, is_bot=False, first_name="Sardor")

FAKE_JPEG = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.requests: list[TelegramMethod] = []
        self.fail_with: Exception | None = None
        self._next_message_id = 1000

    async def close(self) -> None:
        pass

    async def make_request(self, bot, method, timeout=None):
        if self.fail_with is not None:
            raise self.fail_with
        self.requests.append(method)
        if isinstance(method, SendMessage):
            self._next_message_id += 1
            return Message(
                message_id=self._next_message_id,
                date=datetime.now(timezone.utc),
                chat=Chat(id=method.chat_id, type="supergroup"),
                text=method.text,
            )
        if isinstance(method, GetMe):
            return User(id=4242, is_bot=True, first_name="Amora", username="amora_test_bot")
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="unique", file_path="photos/a.jpg")
        return True

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        yield FAKE_JPEG

    # --- testlar uchun qulayliklar ---

    def of_type(self, method_type) -> list:
        return [request for request in self.requests if isinstance(request, method_type)]

    def clear(self) -> None:
        self.requests.clear()

    @property
    def last_screen(self) -> SendMessage | EditMessageText:
        """Foydalanuvchi oxirgi ko'rgan xabar (yangi yuborilgan yoki tahrirlangan)."""
        for request in reversed(self.requests):
            if isinstance(request, SendMessage | EditMessageText):
                return request
        raise AssertionError("Bot hech narsa yubormadi")

    @property
    def last_markup(self) -> InlineKeyboardMarkup | None:
        for request in reversed(self.requests):
            if isinstance(request, SendMessage | EditMessageText | EditMessageReplyMarkup):
                return request.reply_markup
        raise AssertionError("Bot hech narsa yubormadi")


def make_fake_bot() -> Bot:
    return Bot(
        "42:TEST",
        session=FakeSession(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )


def button_labels(markup: InlineKeyboardMarkup | None) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.inline_keyboard for button in row]


def find_button(markup: InlineKeyboardMarkup | None, label: str):
    for row in (markup.inline_keyboard if markup else []):
        for button in row:
            if label in button.text:
                return button
    raise AssertionError(f"«{label}» tugmasi yo'q. Bor tugmalar: {button_labels(markup)}")


class Driver:
    """Botga foydalanuvchi nomidan xabar yuboradi va tugma bosadi."""

    def __init__(self, dispatcher: Dispatcher, bot: Bot):
        self.dispatcher = dispatcher
        self.bot = bot
        self.session: FakeSession = bot.session
        self._update_id = 0
        self._message_id = 0

    async def _feed(self, **kwargs) -> None:
        self._update_id += 1
        await self.dispatcher.feed_update(self.bot, Update(update_id=self._update_id, **kwargs))

    def _message(self, user: User, chat: Chat, **kwargs) -> Message:
        self._message_id += 1
        return Message(
            message_id=self._message_id,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=user,
            **kwargs,
        )

    @staticmethod
    def _user(user_id: int) -> User:
        return User(id=user_id, is_bot=False, first_name="Admin" if user_id == ADMIN_ID else "Begona")

    async def say(self, text: str, user_id: int = ADMIN_ID, chat_id: int | None = None) -> None:
        chat = Chat(id=chat_id or user_id, type="private" if chat_id is None else "supergroup")
        await self._feed(message=self._message(self._user(user_id), chat, text=text))

    async def send_photo(self, user_id: int = ADMIN_ID) -> None:
        photo = [
            PhotoSize(file_id="small", file_unique_id="s", width=90, height=90),
            PhotoSize(file_id="big", file_unique_id="b", width=1280, height=960),
        ]
        chat = Chat(id=user_id, type="private")
        await self._feed(message=self._message(self._user(user_id), chat, photo=photo))

    async def send_location(self, latitude: float, longitude: float, user_id: int = ADMIN_ID) -> None:
        chat = Chat(id=user_id, type="private")
        location = Location(latitude=latitude, longitude=longitude)
        await self._feed(message=self._message(self._user(user_id), chat, location=location))

    async def press_data(
        self, data: str, user: User, chat_id: int, message_id: int = 1, chat_type: str = "private"
    ) -> None:
        message = Message(
            message_id=message_id,
            date=datetime.now(timezone.utc),
            chat=Chat(id=chat_id, type=chat_type),
            text="...",
        )
        self._update_id += 1
        callback = CallbackQuery(
            id=str(self._update_id), from_user=user, chat_instance="x", message=message, data=data
        )
        await self.dispatcher.feed_update(
            self.bot, Update(update_id=self._update_id, callback_query=callback)
        )

    async def press(self, label: str, user_id: int = ADMIN_ID) -> None:
        """Admin oxirgi ko'rgan xabardagi tugmani matni bo'yicha bosadi."""
        button = find_button(self.session.last_markup, label)
        await self.press_data(button.callback_data, self._user(user_id), chat_id=user_id)

    async def press_in_group(self, label: str, message_id: int, user: User = STAFF, chat_id: int = GROUP_ID) -> None:
        """Xodim guruhdagi buyurtma xabari tugmasini bosadi."""
        button = find_button(self.session.last_markup, label)
        await self.press_data(button.callback_data, user, chat_id, message_id, "supergroup")

    @property
    def screen(self) -> str:
        return self.session.last_screen.text

    @property
    def buttons(self) -> list[str]:
        return button_labels(self.session.last_markup)


_dispatcher: Dispatcher | None = None


def get_dispatcher(cfg, session_factory) -> Dispatcher:
    """Router'lar faqat bitta Dispatcher'ga ulanadi, shuning uchun uni qayta ishlatamiz."""
    global _dispatcher
    from app.bot import build_dispatcher

    if _dispatcher is None:
        _dispatcher = build_dispatcher(cfg, session_factory)
    _dispatcher["cfg"] = cfg
    _dispatcher["session_factory"] = session_factory
    _dispatcher.fsm.storage = MemoryStorage()
    return _dispatcher
