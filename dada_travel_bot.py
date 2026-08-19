import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery
)


# ==============================
# НАСТРОЙКИ
# ==============================

BOT_TOKEN = os.environ["BOT_TOKEN"]

CHANNEL_USERNAME = "@dada_travel"
CHANNEL_URL = "https://t.me/dada_travel"
ADVISER_USERNAME = "@dadatravel_adviser"

PDF_FILE = "DaDa_Travel_Theatre_Premieres.pdf"


# ==============================
# БОТ
# ==============================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()


# ==============================
# КЛАВИАТУРЫ
# ==============================

# Показывается, когда пользователь ещё не подписан (первая попытка)
subscribe_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📲 Подписаться на канал",
                url=CHANNEL_URL
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Я подписался, получить гайд",
                callback_data="check_subscription"
            )
        ]
    ]
)

# Показывается, если после нажатия "Я подписался" подписка не найдена
recheck_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📲 Подписаться на канал",
                url=CHANNEL_URL
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Проверить снова",
                callback_data="check_subscription"
            )
        ]
    ]
)


# ==============================
# ПРОВЕРКА ПОДПИСКИ
# ==============================

async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id
        )

        return member.status in {
            "member",
            "administrator",
            "creator"
        }

    except Exception:
        return False


# ==============================
# ОТПРАВКА ГАЙДА (сценарий А)
# ==============================

async def send_guide(message: Message):

    if not os.path.exists(PDF_FILE):
        await message.answer("⚠️ Файл пока не найден.")
        return

    await message.answer_document(
        document=FSInputFile(PDF_FILE),
        caption=(
            "Спасибо за подписку ❤️\n\n"
            "Ловите главные театральные хайлайты сезона!"
        )
    )

    adviser_escaped = ADVISER_USERNAME.replace("_", "\\_")

    await asyncio.sleep(5)

    await message.answer(
        "[ТЕСТ-V2] "
        "Если какой-либо из спектаклей особенно Вас заинтересовал, "
        "будем рады помочь организовать путешествие вокруг него. "
        f"Напишите {adviser_escaped} — составим маршрут, "
        "забронируем рестораны и отели по специальным рейтам и "
        "позаботимся обо всех деталях. А еще, конечно, поможем "
        "попасть на самые востребованные постановки — даже если "
        "билеты уже распроданы!"
    )


# ==============================
# /START
# ==============================

@dp.message(Command("start"))
async def start_handler(message: Message):

    await message.answer(
        "Привет! Это бот авторского бюро путешествий DADA Travel.\n\n"
        "Специально для наших подписчиков мы подготовили гайд по самым "
        "важным театральным премьерам Европы в этом сезоне. "
        f"Подпишитесь на [канал]({CHANNEL_URL}) и мы отправим его Вам!",
        reply_markup=subscribe_keyboard
    )


# ==============================
# /GUIDE
# ==============================

@dp.message(Command("guide"))
async def guide_handler(message: Message):

    if await is_subscribed(message.from_user.id):
        await send_guide(message)
        return

    await message.answer(
        "Вы не подписаны на канал — гайд отправим сразу после подписки.",
        reply_markup=subscribe_keyboard
    )


# ==============================
# ПРОВЕРКА ПОДПИСКИ (по кнопке)
# ==============================

@dp.callback_query(
    lambda callback: callback.data == "check_subscription"
)
async def check_subscription(callback: CallbackQuery):

    if await is_subscribed(callback.from_user.id):

        # убираем кнопки с исходного сообщения, сам текст не трогаем
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await send_guide(callback.message)
        await callback.answer()

    else:

        await callback.message.answer(
            "Пока не вижу Вас среди подписчиков. Проверьте, пожалуйста, "
            "что подписка оформлена, и нажмите кнопку ещё раз.",
            reply_markup=recheck_keyboard
        )

        await callback.answer(
            "❌ Вы ещё не подписались на канал Dada Travel.",
            show_alert=True
        )


# ==============================
# ЗАПУСК
# ==============================

async def main():
    print("=== Файлы рядом с ботом на сервере ===")
    for f in os.listdir("."):
        print(f)
    print("=======================================")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
