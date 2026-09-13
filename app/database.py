# Файл: app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from .config import DB_HOST, DB_NAME, DB_PASS, DB_PORT, DB_USER

# Формируем строку подключения (DSN) к базе данных
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаем асинхронный "движок" для взаимодействия с БД
# echo=True будет выводить в консоль все SQL-запросы, полезно для отладки на первых порах
engine = create_async_engine(DATABASE_URL, echo=True)

# Создаем "фабрику сессий", которая будет создавать сессии для подключения к БД
session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Функция для создания таблиц в БД на основе наших моделей
async def create_db_and_tables():
    from app.models import models
    from app.models.base import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)