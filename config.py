# config.py
# Настройки бота. Читаются из переменных окружения хостинга.

import os

# ---------- Обязательные ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ---------- Интервалы ----------
POST_INTERVAL = int(os.getenv("POST_INTERVAL", "300"))
FULL_CYCLE_DELAY = int(os.getenv("FULL_CYCLE_DELAY", "86400"))

# ---------- Текст поста ----------
POST_TEXT = os.getenv("POST_TEXT", "привет")

# ---------- Файлы ----------
DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "channels.db")
LOG_PATH = os.path.join(DATA_DIR, "bot.log")

# ---------- Проверка ----------
if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN в переменных окружения!")
if not ADMIN_ID:
    raise ValueError("Не задан ADMIN_ID в переменных окружения!")
