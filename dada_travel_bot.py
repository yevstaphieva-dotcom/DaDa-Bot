import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CONFIG
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Please export BOT_TOKEN to run the bot.")

CHANNEL_USERNAME = "@dada_travel"
CHANNEL_URL = "https://t.me/dada_travel"
ADVISER_USERNAME = "@dadatravel_adviser"

PDF_FILE = Path("DaDa_Travel_Theatre_Premieres.pdf")

# Bot and dispatcher
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)
dp = Dispatcher()

# Keyboard helper
def make_subscribe_keyboard(channel_url: str, recheck_text: str = "✅ Я подписался, получить гайд") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📲 Подписаться на канал", url=channel_url)],
            [InlineKeyboardButton(text=recheck_text, callback_data="check_subscription")],
        ]
    )

subscribe_keyboard = make_subscribe_keyboard(CHANNEL_URL)
recheck_keyboard = make_subscribe_keyboard(CHANNEL_URL, recheck_text="🔄 Проверить снова")

# In-memory cache for PDF file_id to avoid re-uploading each time.
# Note: for multi-process instances or restarts you should store file_id persistently.
_cached_pdf_file_id: Optional[str] = None

async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        # Member.status may be an enum — normalize to lowercase string value for robust comparison:
        status_obj = getattr(member, "status", None)
        status_value = getattr(status_obj, "value", str(status_obj)).lower()
        return status_value in {"member", "administrator", "creator"}
    except TelegramForbiddenError:
        # Bot isn't allowed to access chat members of the channel — treat as not subscribed.
        logger.warning("Bot is forbidden to get chat member info for user %s", user_id)
        return False
    except TelegramAPIError as e:
        # Specific aiogram/Telegram API errors — log for debugging
        logger.exception("Telegram API error while checking subscription: %s", e)
        return False
    except Exception:
        # Fallback — log the unexpected error (avoid silent swallowing)
        logger.exception("Unexpected error in is_subscribed()")
        return False

async def send_guide(message: Message):
    global _cached_pdf_file_id

    if not PDF_FILE.exists():
        await message.answer("⚠️ Файл пока не найден.")
        return

    try:
        if _cached_pdf_file_id:
            # Send by file_id (fast, avoids re-upload)
            sent = await message.answer_document(document=_cached_pdf_file_id, caption=(
                "Спасибо за подписку ❤️\n\n"
                "Ловите главные театральные хайлайты сезона!"
            ))
        else:
            # Upload local file and cache returned file_id for future sends
            sent_msg = await message.answer_document(document=FSInputFile(PDF_FILE), caption=(
                "Спасибо за подписку ❤️\n\n"
                "Ловите главные театральные хайлайты сезона!"
            ))
            # message.answer_document returns a Message with document attribute
            doc = getattr(sent_msg, "document", None)
            if doc:
                _cached_pdf_file_id = doc.file_id

        # Escape underscore in username for Markdown mode (keep as is if you change parse mode)
        adviser_escaped = ADVISER_USERNAME.replace("_", "\\_")

        # No artificial sleep — send the follow-up message immediately.
        # If you purposely want a delay, use background tasks or document why.
        await message.answer(
            "Если какой-либо из спектаклей особенно Вас заинтересовал, "
            "будем рады помочь организовать путешествие вокруг него. "
            f"Напишите {adviser_escaped} — составим маршрут вокруг события, "
            "забронируем лучшие отели и рестораны по специальным рейтам и "
            "позаботимся обо всех деталях. И, конечно, поможем попасть на "
            "самые востребованные постановки — даже если билеты уже "
            "распроданы!"
        )
    except TelegramAPIError as e:
        logger.exception("Failed to send guide: %s", e)
        await message.answer("Произошла ошибка при отправке файла. Пожалуйста, попробуйте позже.")

# Example handlers (unchanged flow)
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "Привет! Это бот авторского бюро путешествий DADA Travel.\n\n"
        "Специально для наших подписчиков мы подготовили гайд по самым "
        "важным театральным премьерам Европы в этом сезоне. "
        f"Подпишитесь на [канал]({CHANNEL_URL}) и мы отправим его Вам!",
        reply_markup=subscribe_keyboard
    )

@dp.message(Command("guide"))
async def guide_handler(message: Message):
    user_id = getattr(message.from_user, "id", None)
    if not user_id:
        await message.answer("Не удалось определить пользователя. Пожалуйста, откройте бот в личных сообщениях.")
        return

    if await is_subscribed(user_id):
        await send_guide(message)
        return

    await message.answer(
        "Вы не подписаны на канал — гайд отправим сразу после подписки.",
        reply_markup=subscribe_keyboard
    )

@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription(callback: CallbackQuery):
    user_id = getattr(callback.from_user, "id", None)
    if not user_id:
        await callback.answer("Не могу определить Вас. Попробуйте снова.", show_alert=True)
        return

    if await is_subscribed(user_id):
        # Try to remove inline keyboard; handle only known Telegram errors
        try:
            if callback.message:
                await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramAPIError:
            logger.exception("Unable to remove reply_markup from message")

        if callback.message:
            await send_guide(callback.message)
        await callback.answer()
    else:
        # keep user-friendly messages; avoid raising
        if callback.message:
            await callback.message.answer(
                "Пока не вижу Вас среди подписчиков. Проверьте, пожалуйста, "
                "что подписка оформлена, и нажмите кнопку ещё раз.",
                reply_markup=recheck_keyboard
            )

        await callback.answer("❌ Вы ещё не подписались на канал Dada Travel.", show_alert=True)

# Start polling (unchanged)
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
