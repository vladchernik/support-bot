# Файл: app/middleware.py (ФИНАЛЬНАЯ ВЕРСИЯ БЕЗ КЭША)

import logging
from typing import Callable, Dict, Any, Awaitable

import aiohttp
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import async_sessionmaker

from .config import AUTH_API_BASE_URL, AUTH_API_KEY

# Тексты ответов остаются
REJECTION_TEXT = "У вас нет доступа к этому боту. Пожалуйста, зайдите с рабочего аккаунта."
NO_USERNAME_TEXT = "Для использования бота у вас должен быть установлен username в настройках Telegram."
API_ERROR_TEXT = "Сервис авторизации временно недоступен. Попробуйте позже."

async def reject_user(event: TelegramObject, text: str):
    if isinstance(event, Message):
        await event.answer(text)
    elif isinstance(event, CallbackQuery):
        await event.message.answer(text)
        await event.answer()


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        user = data.get('event_from_user')

        if not user:
            return await handler(event, data)
        
        bot: Bot = data.get('bot')
        if bot and user.id == bot.id:
            return await handler(event, data)
        
        # --------------------------------------------------------------------
        # ИЗМЕНЕНИЕ 1: Полностью удален блок проверки кэша.
        # Теперь мы всегда идем дальше, к проверке по API.
        # --------------------------------------------------------------------

        username = user.username
        if not username:
            # Запись в кэш удалена
            await reject_user(event, NO_USERNAME_TEXT)
            return

        api_username = f"@{username}"
        api_url = f"{AUTH_API_BASE_URL}/tgUserExists/{api_username}"
        headers = {"x-api-key": AUTH_API_KEY}
        is_authorized = False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        is_authorized = await response.json() is True
                    else:
                        logging.error(f"Auth API Error: Status {response.status}, Body: {await response.text()}")
        
        except Exception as e:
            logging.critical(f"Auth API CRITICAL ERROR for @{username}: {e}")
            await reject_user(event, API_ERROR_TEXT)
            return

        # --------------------------------------------------------------------
        # ИЗМЕНЕНИЕ 2: Принимаем решение сразу, без сохранения в кэш.
        # --------------------------------------------------------------------
        if is_authorized:
            return await handler(event, data)
        else:
            await reject_user(event, REJECTION_TEXT)
            return


# Middleware для передачи сессии базы данных в обработчики
class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Создаем сессию из пула перед вызовом обработчика
        async with self.session_pool() as session:
            # "Прокидываем" сессию в data, чтобы она была доступна в хэндлере
            data["session"] = session
            # Вызываем следующий обработчик в цепочке
            return await handler(event, data)
