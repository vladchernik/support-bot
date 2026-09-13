# Файл: app/handlers/user_handlers.py

import logging
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.models import Ticket, TicketMessage
from app.config import SUPPORT_GROUP_ID, ICON_INCOMING, WELCOME_MESSAGE

router = Router()
user_locks = {}


@router.message(CommandStart())
async def handle_start(message: Message):
    user_name = message.from_user.full_name
    welcome_text = WELCOME_MESSAGE.format(user_name=user_name)
    await message.answer(welcome_text)
    try:
        await message.delete()
    except Exception as e:
        print(f"Не удалось удалить сообщение: {e}")


@router.message(F.chat.type == "private")
async def handle_user_message(message: Message, bot: Bot, session: AsyncSession):
    user_id = message.from_user.id
    lock = user_locks.setdefault(user_id, asyncio.Lock())

    async with lock:
        query = select(Ticket).where(Ticket.user_id == user_id)
        result = await session.execute(query)
        existing_ticket = result.scalar_one_or_none()

        if existing_ticket is None:
            try:
                topic_id_to_forward = await create_new_ticket_with_card(message, bot, session)
            except IntegrityError:
                await session.rollback()
                logging.warning(f"Произошла гонка состояний для user_id {user_id}. Повторный поиск.")
                query = select(Ticket).where(Ticket.user_id == user_id)
                result = await session.execute(query)
                existing_ticket = result.scalar_one()
                topic_id_to_forward = existing_ticket.topic_id

                # Сохраняем сообщение пользователя для существующего тикета
                await save_user_message(message, existing_ticket.id, session)
        else:
            try:
                topic_id_to_forward = existing_ticket.topic_id

                # Попытка "переоткрыть" тему, если она была закрыта
                if existing_ticket.status in ['closed', 'answered']:
                    await bot.edit_forum_topic(
                        chat_id=SUPPORT_GROUP_ID,
                        message_thread_id=topic_id_to_forward,
                        icon_custom_emoji_id=ICON_INCOMING
                    )
                    existing_ticket.status = 'open'
                    await session.commit()

                # Сохраняем сообщение пользователя в БД
                await save_user_message(message, existing_ticket.id, session)

                # Отправляем сообщение в группу
                await bot.copy_message(
                    chat_id=SUPPORT_GROUP_ID,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    message_thread_id=topic_id_to_forward
                )
                return

            except TelegramBadRequest as e:
                if "message thread not found" in str(e).lower() or "topic_id_invalid" in str(e).lower():
                    logging.warning(f"Тема {existing_ticket.topic_id} не найдена. Создаю новую.")
                    topic_id_to_forward = await recreate_topic_with_card(existing_ticket, message, bot, session)
                    # Сохраняем сообщение после создания новой темы
                    await save_user_message(message, existing_ticket.id, session)
                elif "topic_not_modified" in str(e).lower():
                    logging.warning("Попытка изменить иконку на ту же самую. Игнорирую.")
                    topic_id_to_forward = existing_ticket.topic_id
                    await save_user_message(message, existing_ticket.id, session)
                else:
                    logging.error(f"Неожиданная ошибка Telegram: {e}")
                    raise

        # Отправляем сообщение (если не вышли из функции ранее)
        await bot.copy_message(
            chat_id=SUPPORT_GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=topic_id_to_forward
        )


# Сохранение сообщения пользователя в таблицу TicketMessage
async def save_user_message(message: Message, ticket_id: int, session: AsyncSession):

    # Определяем текст сообщения с пометками для медиа
    if message.photo:
        message_text = "[PHOTO]"
        if message.caption:
            message_text += f" {message.caption}"
    elif message.document:
        message_text = "[DOCUMENT]"
        if message.caption:
            message_text += f" {message.caption}"
    elif message.video:
        message_text = "[VIDEO]"
        if message.caption:
            message_text += f" {message.caption}"
    elif message.audio:
        message_text = "[AUDIO]"
        if message.caption:
            message_text += f" {message.caption}"
    elif message.voice:
        message_text = "[VOICE]"
        if message.caption:
            message_text += f" {message.caption}"
    elif message.sticker:
        message_text = f"[STICKER] {message.sticker.emoji or ''}"
    elif message.text:
        message_text = message.text
    else:
        message_text = "[UNKNOWN_MEDIA]"

    # Создание записи в БД
    new_message = TicketMessage(
        ticket_id=ticket_id,
        sender_type='user',
        sender_id=message.from_user.id,
        message_text=message_text[:1000]  # Ограничение длины текста до 1000 символов
    )

    session.add(new_message)
    await session.commit()


async def create_new_ticket_with_card(message: Message, bot: Bot, session: AsyncSession) -> int:
    topic = await bot.create_forum_topic(
        chat_id=SUPPORT_GROUP_ID,
        name=f"Обращение от {message.from_user.full_name}",
        icon_custom_emoji_id=ICON_INCOMING
    )

    user = message.from_user
    user_link = f"https://telegram.me/{user.username}" if user.username else user.url
    user_card = (
        f"<b>КОНТАКТНАЯ ИНФОРМАЦИЯ</b>\n"
        f"ID: <code>{user.id}</code>\n"
        f"Ссылка: {user_link}"
    )
    await bot.send_message(
        chat_id=SUPPORT_GROUP_ID,
        text=user_card,
        message_thread_id=topic.message_thread_id
    )

    new_ticket = Ticket(
        user_id=user.id,
        user_firstname=user.first_name,
        user_lastname=user.last_name,
        topic_id=topic.message_thread_id,
        status='open'
    )
    session.add(new_ticket)
    await session.commit()

    # Сохраняем первое сообщение пользователя
    await save_user_message(message, new_ticket.id, session)

    return topic.message_thread_id


async def recreate_topic_with_card(ticket: Ticket, message: Message, bot: Bot, session: AsyncSession) -> int:
    topic = await bot.create_forum_topic(
        chat_id=SUPPORT_GROUP_ID,
        name=f"Обращение от {message.from_user.full_name}",
        icon_custom_emoji_id=ICON_INCOMING
    )

    user = message.from_user
    user_link = f"https://telegram.me/{user.username}" if user.username else user.url
    user_card = (
        f"<b>КОНТАКТНАЯ ИНФОРМАЦИЯ</b>\n"
        f"ID: <code>{user.id}</code>\n"
        f"Ссылка: {user_link}"
    )
    await bot.send_message(
        chat_id=SUPPORT_GROUP_ID,
        text=user_card,
        message_thread_id=topic.message_thread_id
    )

    ticket.topic_id = topic.message_thread_id
    ticket.status = 'open'
    await session.commit()
    return topic.message_thread_id