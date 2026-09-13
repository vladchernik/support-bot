# Файл: app/config.py

import os
from dotenv import load_dotenv
import textwrap

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем значения. Используем os.getenv, чтобы не было ошибки, если переменная отсутствует
BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPPORT_GROUP_ID = os.getenv('SUPPORT_GROUP_ID')

# Данные для подключения к базе данных
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_NAME = os.getenv('DB_NAME')

# --- pgAdmin ---
PGADMIN_DEFAULT_EMAIL = os.getenv('PGADMIN_DEFAULT_EMAIL')
PGADMIN_DEFAULT_PASSWORD = os.getenv('PGADMIN_DEFAULT_PASSWORD')

# --- Настройки для API авторизации ---
AUTH_API_BASE_URL = os.getenv("AUTH_API_BASE_URL")
AUTH_API_KEY = os.getenv("AUTH_API_KEY")

# ID кастомных эмодзи для иконок тем
# 📩 Иконка "Входящее"
ICON_INCOMING = '5417915203100613993'
# ✅ Иконка "Отвечено"
ICON_OUTGOING = '5237699328843200968'

# --- Функциональные флаги ---
ENABLE_SPED_COMMAND = os.getenv('ENABLE_SPED_COMMAND', 'False').lower() in ('true', '1', 't')
ENABLE_ADMIN_COMMAND = os.getenv('ENABLE_ADMIN_COMMAND', 'False').lower() in ('true', '1', 't')
ENABLE_DONE_COMMAND = os.getenv('ENABLE_DONE_COMMAND', 'False').lower() in ('true', '1', 't')
BOT_PERSONALITY = os.getenv('BOT_PERSONALITY', 'default') # Читаем тип бота

# --- Хранилище текстов ---
# Здесь мы храним все наши большие тексты в удобном формате
TEXTS = {
    "admins": {
        "welcome": """<b>Здравствуйте, {user_name}! Добро пожаловать в наш телеграм-бот IT-поддержки!</b>

Мы здесь, чтобы помочь вам с вопросами по обслуживанию корпоративной сети, офисной оргтехники, компьютеров и внутренним сетевым ресурсам. Чтобы мы могли быстрее обработать ваш запрос, пожалуйста, попробуйте структурировать его следующим образом:

- <i><b>Тип проблемы</b> (например, не работает принтер, проблемы с интернетом и т.д.)</i>
- <i><b>Описание ситуации</b> (что именно случилось, когда возникла проблема)</i>
- <i><b>Уровень срочности</b> (критично, в течение рабочего дня, стандарты и т.д.)</i>
- <i><b>Фото или скриншот</b> с проблемой</i>\n\n

Спасибо, что помогаете нам повысить качество обслуживания! Если у вас возникнут вопросы, не стесняйтесь писать – мы всегда готовы помочь!"""
    },
    "default": {
        "welcome": """<b>Здравствуйте, {user_name}!</b>\n\nОпишите вашу проблему."""
    }
}

# Выбираем нужный текст приветствия на основе типа бота
raw_welcome_message = TEXTS.get(BOT_PERSONALITY, TEXTS["default"])["welcome"]
WELCOME_MESSAGE = textwrap.dedent(raw_welcome_message).strip()

# Проверяем, что токен бота и ID группы указаны, так как без них бот не запустится
if not BOT_TOKEN:
    raise ValueError("Необходимо указать токен бота в файле .env (BOT_TOKEN)")
if not SUPPORT_GROUP_ID:
    raise ValueError("Необходимо указать ID группы поддержки в файле .env (SUPPORT_GROUP_ID)")
    