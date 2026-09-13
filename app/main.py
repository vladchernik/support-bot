import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import BOT_TOKEN, ENABLE_SPED_COMMAND, ENABLE_ADMIN_COMMAND, ENABLE_DONE_COMMAND
from .database import create_db_and_tables, session_maker
from .handlers import user_handlers, admin_handlers
from .middleware import DbSessionMiddleware, AuthMiddleware


async def main():
    await create_db_and_tables()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    dp.message.middleware(AuthMiddleware())
    dp.update.middleware(DbSessionMiddleware(session_pool=session_maker))

    # 1. Роутер пользователя (он работает в личке, поэтому не конфликтует)
    dp.include_router(user_handlers.router)

    # 2. Сначала регистрируем СПЕЦИФИЧНЫЕ роутеры для команд /sped, /admin, /done
    if ENABLE_SPED_COMMAND:
        dp.include_router(admin_handlers.sped_router)
        logging.info("Команда /sped включена.")
    else:
        logging.info("Команда /sped отключена.")

    if ENABLE_ADMIN_COMMAND:
        dp.include_router(admin_handlers.admin_router)
        logging.info("Команда /admin включена.")
    else:
        logging.info("Команда /admin отключена.")

    if ENABLE_DONE_COMMAND:
        dp.include_router(admin_handlers.done_router)
        logging.info("Команда /done включена.")
    else:
        logging.info("Команда /done отключена.")

    # 3. Регистрируем роутер для статистики
    if hasattr(admin_handlers, 'stats_router'):
        dp.include_router(admin_handlers.stats_router)
        logging.info("Команда /stats включена.")
    else:
        logging.warning("Роутер для статистики не найден.")

    # 4. И только в самом конце регистрируем ОБЩИЙ роутер для всех остальных сообщений от админа
    dp.include_router(admin_handlers.common_admin_router)

    logging.info("Бот запущен и готов к работе!")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Работа бота прервана")