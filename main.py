# main.py
# Бот-автопостер:
#   - Ловит добавление в канал (ChatMemberUpdated).
#   - По кругу постит «привет» в каналы с интервалом POST_INTERVAL.
#   - После обхода всех каналов ждёт FULL_CYCLE_DELAY (24 часа).

import asyncio
import logging
import random
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated

from config import (
    BOT_TOKEN, ADMIN_ID, POST_INTERVAL, FULL_CYCLE_DELAY, POST_TEXT,
    LOG_PATH,
)
import database as db


# ---------- Логирование ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ============================================================
#              АВТОДОБАВЛЕНИЕ КАНАЛОВ
# ============================================================

@dp.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated):
    """
    Срабатывает, когда бот меняет свой статус в чате.
    Нас интересует, когда бота ДОБАВИЛИ как администратора канала.
    """
    chat = event.chat
    new_status = event.new_chat_member.status

    # Интересует только канал
    if chat.type != "channel":
        return

    # Бот стал администратором
    if new_status in ("administrator", "creator", "member"):
        name = chat.title or str(chat.id)

        # Игнорируем, если это уже был админ — не спамим
        if event.old_chat_member.status in ("administrator", "creator", "member"):
            return

        await db.add_channel(chat.id, name)
        logger.info(f"✅ Добавлен канал: {name} ({chat.id})")

        # Уведомление админу
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"✅ <b>Добавлен канал:</b>\n"
                    f"📛 {name}\n"
                    f"🆔 <code>{chat.id}</code>"
                )
            )
        except Exception as e:
            logger.error(f"Не смог уведомить админа: {e}")

    # Бота удалили из канала
    elif new_status in ("left", "kicked"):
        # Можно пометить канал как выключенный
        await db.set_channel_status(chat.id, 1)
        logger.info(f"❌ Бот удалён из канала: {chat.title} ({chat.id})")


# ============================================================
#              КОМАНДЫ АДМИНА
# ============================================================

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Бот приватный.")
        return
    await message.answer(
        "👋 <b>Бот-автопостер</b>\n\n"
        "<b>Команды:</b>\n"
        "/start_posting — запустить постинг\n"
        "/stop_posting — остановить постинг\n"
        "/status — статус\n"
        "/list_channels — список каналов\n"
    )


@dp.message(Command("start_posting"))
async def cmd_start_posting(message: Message):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("posting", "1")
    await message.answer("▶️ Постинг <b>запущен</b>.")
    logger.info("Постинг запущен админом.")


@dp.message(Command("stop_posting"))
async def cmd_stop_posting(message: Message):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("posting", "0")
    await message.answer("⏸ Постинг <b>остановлен</b>.")
    logger.info("Постинг остановлен админом.")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    if not is_admin(message.from_user.id):
        return
    active = await db.get_setting("posting", "0")
    total = await db.count_channels()

    status_line = "▶️ работает" if active == "1" else "⏸ остановлен"

    await message.answer(
        f"📊 <b>Статус</b>\n\n"
        f"Постинг: {status_line}\n"
        f"Каналов активных: <b>{total}</b>\n"
        f"Интервал между постами: {POST_INTERVAL} сек\n"
        f"Пауза между кругами: {FULL_CYCLE_DELAY // 3600} ч"
    )


@dp.message(Command("list_channels"))
async def cmd_list_channels(message: Message):
    if not is_admin(message.from_user.id):
        return
    channels = await db.get_channels(active_only=False)
    if not channels:
        await message.answer("📭 Каналов нет. Добавь бота в канал.")
        return

    lines = ["📋 <b>Каналы:</b>\n"]
    for row in channels:
        # Если активный запрос (4 поля) — старая структура
        if len(row) == 4:
            cid, ch_id, name, last = row
            status = 0
        else:
            cid, ch_id, name, last, status = row

        mark = "🟢" if status == 0 else "🔴"
        last_str = last or "—"
        lines.append(f"{mark} <b>{name}</b>\n   ID: <code>{ch_id}</code>\n   Последний пост: {last_str}\n")

    await message.answer("\n".join(lines))


# ============================================================
#              ФОНОВЫЙ ПОСТИНГ
# ============================================================

async def poster_loop():
    """
    Бесконечный цикл:
    1. Берём все активные каналы.
    2. По очереди постим в каждый с интервалом POST_INTERVAL.
    3. После обхода всех — ждём FULL_CYCLE_DELAY.
    Повторяем.
    """
    logger.info("Постинг-цикл запущен.")
    while True:
        try:
            # Проверяем, включён ли постинг
            enabled = await db.get_setting("posting", "0")
            if enabled != "1":
                await asyncio.sleep(30)
                continue

            channels = await db.get_channels(active_only=True)
            if not channels:
                logger.info("Нет активных каналов — жду 5 минут.")
                await asyncio.sleep(300)
                continue

            logger.info(f"🔁 Начинаю круг: {len(channels)} каналов.")

            for row in channels:
                cid, ch_id, name, last = row

                # Отправляем пост
                try:
                    await bot.send_message(chat_id=ch_id, text=POST_TEXT)
                    await db.mark_posted(ch_id)
                    logger.info(f"✅ Пост в «{name}» ({ch_id})")
                except Exception as e:
                    logger.error(f"❌ Ошибка поста в «{name}» ({ch_id}): {e}")

                # Ждём интервал до следующего канала
                await asyncio.sleep(POST_INTERVAL)

            logger.info(f"✅ Круг завершён. Жду {FULL_CYCLE_DELAY // 3600} ч.")
            await asyncio.sleep(FULL_CYCLE_DELAY)

        except Exception as e:
            logger.error(f"Ошибка в постинг-цикле: {e}")
            await asyncio.sleep(60)


# ============================================================
#              ЗАПУСК
# ============================================================

async def main():
    await db.init_db()
    logger.info(f"Бот-автопостер запущен. Админ: {ADMIN_ID}")

    # Запускаем постинг-цикл параллельно с polling
    asyncio.create_task(poster_loop())

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")