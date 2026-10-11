# database.py
# Работа с SQLite: каналы и их статусы.

import os
import aiosqlite
from datetime import datetime

from config import DB_PATH

# Создаём папку data/, если её нет
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


async def init_db():
    """Создаёт таблицу channels, если её ещё нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id      INTEGER UNIQUE NOT NULL,
                channel_name    TEXT,
                last_post_time  TIMESTAMP,
                status          INTEGER DEFAULT 0
            )
        """)
        # Настройки бота (например, "постинг включён/выключен")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key    TEXT PRIMARY KEY,
                value  TEXT
            )
        """)
        await db.commit()


# ---------- Каналы ----------
async def add_channel(channel_id: int, channel_name: str):
    """Добавляет канал. Если уже есть — обновляет имя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO channels (channel_id, channel_name) VALUES (?, ?) "
            "ON CONFLICT(channel_id) DO UPDATE SET channel_name = excluded.channel_name",
            (channel_id, channel_name)
        )
        await db.commit()


async def get_channels(active_only: bool = True) -> list[tuple]:
    """Возвращает список каналов."""
    async with aiosqlite.connect(DB_PATH) as db:
        if active_only:
            cur = await db.execute(
                "SELECT id, channel_id, channel_name, last_post_time "
                "FROM channels WHERE status = 0 ORDER BY id"
            )
        else:
            cur = await db.execute(
                "SELECT id, channel_id, channel_name, last_post_time, status "
                "FROM channels ORDER BY id"
            )
        return await cur.fetchall()


async def count_channels() -> int:
    """Сколько активных каналов."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM channels WHERE status = 0")
        row = await cur.fetchone()
        return row[0] if row else 0


async def mark_posted(channel_id: int):
    """Обновляет время последнего поста в канале."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE channels SET last_post_time = ? WHERE channel_id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), channel_id)
        )
        await db.commit()


async def set_channel_status(channel_id: int, status: int):
    """Меняет статус канала (0 — активен, 1 — выключен)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE channels SET status = ? WHERE channel_id = ?",
            (status, channel_id)
        )
        await db.commit()


# ---------- Настройки ----------
async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        await db.commit()


async def get_setting(key: str, default: str = None) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default