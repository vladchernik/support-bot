# Файл: app/handlers/admin_handlers.py

import io
import csv
from datetime import datetime, timedelta
from typing import Optional
from aiogram.types import BufferedInputFile
from sqlalchemy import select, func, and_, extract
from sqlalchemy.sql import text
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, MessageOriginUser, MessageOriginChannel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.models import Ticket, TicketMessage
from app.config import ICON_OUTGOING, ICON_INCOMING

# Разделяем на два роутера
common_admin_router = Router()
sped_router = Router()
admin_router = Router()
done_router = Router()

# Создание отдельного роутера для статистики
stats_router = Router()


# --------------------------------------------------------------------
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ СОХРАНЕНИЯ СООБЩЕНИЙ САППОРТА
# --------------------------------------------------------------------
async def save_admin_message(message: Message, ticket_id: int, session: AsyncSession):

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
    elif message.video_note:
        message_text = "[VIDEO_NOTE]"
    elif message.text:
        # Если это пересланное сообщение, добавляем пометку
        if message.forward_origin:
            origin = message.forward_origin
            if isinstance(origin, MessageOriginUser):
                sender_name = origin.sender_user.full_name
                message_text = f"[FORWARD from {sender_name}] {message.text}"
            elif isinstance(origin, MessageOriginChannel):
                channel_name = origin.chat.title
                message_text = f"[FORWARD from channel {channel_name}] {message.text}"
            else:
                message_text = f"[FORWARD] {message.text}"
        else:
            message_text = message.text
    else:
        message_text = "[UNKNOWN_MEDIA]"

    # Создаем запись в БД (created_at не указываем - БД сама установит время)
    new_message = TicketMessage(
        ticket_id=ticket_id,
        sender_type='support',
        sender_id=message.from_user.id,
        message_text=message_text[:1000]  # Ограничиваем длину текста
    )

    session.add(new_message)
    await session.commit()


# --------------------------------------------------------------------
# ОБРАБОТЧИК 1: КОНКРЕТНАЯ КОМАНДА /close
# --------------------------------------------------------------------
@common_admin_router.message(Command("close"), F.chat.is_forum == True, F.message_thread_id)
async def handle_close_command(message: Message, bot: Bot, session: AsyncSession):
    query = select(Ticket).where(Ticket.topic_id == message.message_thread_id)
    result = await session.execute(query)
    ticket = result.scalar_one_or_none()
    if not ticket or ticket.status == 'answered':
        try:
            await message.delete()
        except Exception:
            pass
        return
    ticket.status = 'answered'
    await session.commit()
    try:
        await bot.edit_forum_topic(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            icon_custom_emoji_id=ICON_OUTGOING
        )
        await message.delete()
    except Exception as e:
        print(f"Не удалось изменить иконку или удалить сообщение при 'закрытии': {e}")


# --------------------------------------------------------------------
# ОБРАБОТЧИК 2: КОНКРЕТНАЯ КОМАНДА /open
# --------------------------------------------------------------------
@common_admin_router.message(Command("open"), F.chat.is_forum == True, F.message_thread_id)
async def handle_open_command(message: Message, bot: Bot, session: AsyncSession):
    query = select(Ticket).where(Ticket.topic_id == message.message_thread_id)
    result = await session.execute(query)
    ticket = result.scalar_one_or_none()
    if not ticket or ticket.status == 'open':
        try:
            await message.delete()
        except Exception:
            pass
        return
    ticket.status = 'open'
    await session.commit()
    try:
        await bot.edit_forum_topic(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            icon_custom_emoji_id=ICON_INCOMING
        )
        await message.delete()
    except Exception as e:
        print(f"Не удалось изменить иконку или удалить сообщение при 'открытии': {e}")


# --------------------------------------------------------------------
# ОБРАБОТЧИК 3: НОВАЯ КОМАНДА /sped
# --------------------------------------------------------------------
@sped_router.message(Command("sped"), F.chat.is_forum == True, F.message_thread_id)
async def handle_sped_command(message: Message, bot: Bot, session: AsyncSession):
    """Отправляет пользователю шаблонное сообщение с просьбой обратиться в профильный бот."""
    query = select(Ticket).where(Ticket.topic_id == message.message_thread_id)
    result = await session.execute(query)
    ticket = result.scalar_one_or_none()

    if not ticket or ticket.status == 'answered':
        try:
            await message.delete()
        except Exception:
            pass
        return

    template_text = "Обратитесь с этим вопросом в профильный бот"

    try:
        # Отправляем шаблон пользователю
        await bot.send_message(chat_id=ticket.user_id, text=template_text)

        # Сохраняем сообщение саппорта в БД
        await save_admin_message(message, ticket.id, session)

        # Меняем статус и иконку
        ticket.status = 'answered'
        await session.commit()
        await bot.edit_forum_topic(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            icon_custom_emoji_id=ICON_OUTGOING
        )

        # Удаляем команду из чата
        await message.delete()
    except Exception as e:
        await message.reply(f"Не удалось отправить шаблонное сообщение: {e}")
        print(f"Ошибка при отправке шаблона /sped: {e}")


# --------------------------------------------------------------------
# ОБРАБОТЧИК 4: НОВАЯ КОМАНДА /admin
# --------------------------------------------------------------------
@admin_router.message(Command("admin"), F.chat.is_forum == True, F.message_thread_id)
async def handle_admin_command(message: Message, bot: Bot, session: AsyncSession):
    """Отправляет пользователю шаблонное сообщение с просьбой обратиться в профильный бот."""
    query = select(Ticket).where(Ticket.topic_id == message.message_thread_id)
    result = await session.execute(query)
    ticket = result.scalar_one_or_none()

    if not ticket or ticket.status == 'answered':
        try:
            await message.delete()
        except Exception:
            pass
        return

    template_text = "Обратитесь с этим вопросом в профильный бот"

    try:
        # Отправляем шаблон пользователю
        await bot.send_message(chat_id=ticket.user_id, text=template_text)

        # Сохраняем сообщение саппорта в БД
        await save_admin_message(message, ticket.id, session)

        # Меняем статус и иконку
        ticket.status = 'answered'
        await session.commit()
        await bot.edit_forum_topic(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            icon_custom_emoji_id=ICON_OUTGOING
        )

        # Удаляем команду из чата
        await message.delete()
    except Exception as e:
        await message.reply(f"Не удалось отправить шаблонное сообщение: {e}")
        print(f"Ошибка при отправке шаблона /admin: {e}")


# --------------------------------------------------------------------
# ОБРАБОТЧИК 5: НОВАЯ КОМАНДА /done
# --------------------------------------------------------------------
@done_router.message(Command("done"), F.chat.is_forum == True, F.message_thread_id)
async def handle_done_command(message: Message, bot: Bot, session: AsyncSession):
    """Отправляет пользователю шаблонное сообщение о выполненных изменениях."""
    query = select(Ticket).where(Ticket.topic_id == message.message_thread_id)
    result = await session.execute(query)
    ticket = result.scalar_one_or_none()

    if not ticket or ticket.status == 'answered':
        try:
            await message.delete()
        except Exception:
            pass
        return

    template_text = ("Изменения выполнены. Закройте профиль без сохранения, если открыт. "
                     "Обновите раздел и проверьте данные.")

    try:
        # Отправляем шаблон пользователю
        await bot.send_message(chat_id=ticket.user_id, text=template_text)

        # Сохраняем сообщение саппорта в БД
        await save_admin_message(message, ticket.id, session)

        # Меняем статус и иконку
        ticket.status = 'answered'
        await session.commit()
        await bot.edit_forum_topic(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            icon_custom_emoji_id=ICON_OUTGOING
        )

        # Удаляем команду из чата
        await message.delete()
    except Exception as e:
        await message.reply(f"Не удалось отправить шаблонное сообщение: {e}")


# --------------------------------------------------------------------
# ОБРАБОТЧИК 6: СЛУЖЕБНЫЕ СООБЩЕНИЯ
# --------------------------------------------------------------------
@common_admin_router.message(F.forum_topic_edited)
async def handle_topic_edited_service_message(message: Message):
    """Удаляет служебные сообщения об изменении темы."""
    logging.info(f"Пойман 'forum_topic_edited' для удаления. Message ID: {message.message_id}")
    try:
        await message.delete()
    except Exception as e:
        logging.error(f"Не удалось удалить служебное сообщение: {e}")


# --------------------------------------------------------------------
# ОБРАБОТЧИК 7: ОБЩИЕ СООБЩЕНИЯ ОТ АДМИНА
# --------------------------------------------------------------------
@common_admin_router.message(F.chat.is_forum == True, F.message_thread_id)
async def handle_admin_message(message: Message, bot: Bot, session: AsyncSession):
    if message.from_user.id == bot.id:
        return

    query = select(Ticket).where(Ticket.topic_id == message.message_thread_id)
    result = await session.execute(query)
    ticket = result.scalar_one_or_none()

    if not ticket:
        return

    try:
        # Сохраняем сообщение саппорта в БД (перед отправкой пользователю)
        await save_admin_message(message, ticket.id, session)

        # Новая логика

        # Если это пересланное сообщение
        if message.forward_origin:
            origin = message.forward_origin
            header = "<b>Переслано:</b>\n\n"  # Общий заголовок

            if isinstance(origin, MessageOriginUser):
                sender_name = origin.sender_user.full_name
                header = f"<b>Переслано от {sender_name}:</b>\n\n"
            elif isinstance(origin, MessageOriginChannel):
                channel_name = origin.chat.title
                header = f"<b>Переслано из канала «{channel_name}»:</b>\n\n"

            # Отправляем заголовок и текст (если он есть) одним сообщением
            if message.text:
                await bot.send_message(ticket.user_id, header + message.text)
            else:
                await bot.send_message(ticket.user_id, header)

        # Отправляем контент (фото, видео и т.д.)
        if message.photo:
            await bot.send_photo(ticket.user_id, message.photo[-1].file_id, caption=message.caption)
        elif message.video:
            await bot.send_video(ticket.user_id, message.video.file_id, caption=message.caption)
        elif message.document:
            await bot.send_document(ticket.user_id, message.document.file_id, caption=message.caption)
        elif message.voice:
            await bot.send_voice(ticket.user_id, message.voice.file_id, caption=message.caption)
        elif message.video_note:
            await bot.send_video_note(ticket.user_id, message.video_note.file_id)
        # Если это обычное текстовое сообщение (не пересланное)
        elif message.text and not message.forward_origin:
            await bot.send_message(ticket.user_id, message.text)

        # Логика смены статуса и иконки
        if ticket.status == 'open':
            await bot.edit_forum_topic(
                chat_id=message.chat.id,
                message_thread_id=message.message_thread_id,
                icon_custom_emoji_id=ICON_OUTGOING
            )
            ticket.status = 'answered'
            await session.commit()

    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения админа пользователю {ticket.user_id}: {e}")
        await message.reply(f"Произошла ошибка при доставке сообщения: {e}")


# --------------------------------------------------------------------
# ОБРАБОТЧИК КОМАНДЫ /stats (ДЛЯ АДМИНИСТРАТОРОВ)
# --------------------------------------------------------------------
@stats_router.message(Command("stats"), F.chat.is_forum == True)
async def handle_stats_command(message: Message, session: AsyncSession, bot: Bot):
    """
    Формирует и отправляет статистику за текущую неделю в формате CSV.
    Команда доступна только в форумных группах (для админов).
    """

    # Проверяем, что пользователь является администратором группы
    try:
        chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if chat_member.status not in ['administrator', 'creator']:
            await message.reply("Эта команда доступна только администраторам.")
            return
    except Exception as e:
        logging.error(f"Ошибка проверки прав администратора: {e}")
        await message.reply("Не удалось проверить ваши права.")
        return

    # Показываем, что начали генерацию
    processing_msg = await message.reply("Собираю статистику... Подождите немного.")

    try:
        # Получаем статистику за последние 7 дней (неделю)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        # 1. Статистика по тикетам
        tickets_stats = await get_tickets_stats(session, start_date, end_date)

        # 2. Статистика по сообщениям
        messages_stats = await get_messages_stats(session, start_date, end_date)

        # 3. Детальная статистика по дням
        daily_stats = await get_daily_stats(session, start_date, end_date)

        # 4. Топ пользователей по активности
        top_users = await get_top_users(session, start_date, end_date)

        # 5. Среднее время ответа саппорта
        avg_response_time = await get_avg_response_time(session, start_date, end_date)

        # Формируем CSV файл
        csv_data = generate_csv_report(
            tickets_stats,
            messages_stats,
            daily_stats,
            top_users,
            avg_response_time,
            start_date,
            end_date
        )

        # Отправляем файл
        await send_csv_file(message, csv_data, start_date, end_date)

        # Удаляем сообщение о генерации
        await processing_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка при генерации статистики: {e}")
        await processing_msg.edit_text(f"Произошла ошибка при генерации статистики: {e}")


# --------------------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ СТАТИСТИКИ
# --------------------------------------------------------------------

# Получение общей статистики по тикетам за период
async def get_tickets_stats(session: AsyncSession, start_date: datetime, end_date: datetime):

    # Общее количество тикетов
    total_query = select(func.count()).select_from(Ticket)
    total_result = await session.execute(total_query)
    total_tickets = total_result.scalar() or 0

    # Тикеты созданные за период
    created_query = select(func.count()).select_from(Ticket).where(
        Ticket.id.in_(
            select(Ticket.id).where(
                Ticket.id.in_(
                    select(TicketMessage.ticket_id).where(
                        TicketMessage.created_at.between(start_date, end_date)
                    )
                )
            )
        )
    )
    created_result = await session.execute(created_query)
    created_tickets = created_result.scalar() or 0

    # Закрытые тикеты
    closed_query = select(func.count()).select_from(Ticket).where(
        Ticket.status == 'answered'
    )
    closed_result = await session.execute(closed_query)
    closed_tickets = closed_result.scalar() or 0

    # Открытые тикеты
    open_query = select(func.count()).select_from(Ticket).where(
        Ticket.status == 'open'
    )
    open_result = await session.execute(open_query)
    open_tickets = open_result.scalar() or 0

    return {
        'total': total_tickets,
        'created': created_tickets,
        'closed': closed_tickets,
        'open': open_tickets,
        'closed_percent': round((closed_tickets / total_tickets * 100) if total_tickets > 0 else 0, 2)
    }


# Получение статистики по сообщениям за период
async def get_messages_stats(session: AsyncSession, start_date: datetime, end_date: datetime):

    # Общее количество сообщений за период
    total_query = select(func.count()).select_from(TicketMessage).where(
        TicketMessage.created_at.between(start_date, end_date)
    )
    total_result = await session.execute(total_query)
    total_messages = total_result.scalar() or 0

    # Сообщения от пользователей
    user_query = select(func.count()).select_from(TicketMessage).where(
        and_(
            TicketMessage.created_at.between(start_date, end_date),
            TicketMessage.sender_type == 'user'
        )
    )
    user_result = await session.execute(user_query)
    user_messages = user_result.scalar() or 0

    # Сообщения от саппорта
    support_query = select(func.count()).select_from(TicketMessage).where(
        and_(
            TicketMessage.created_at.between(start_date, end_date),
            TicketMessage.sender_type == 'support'
        )
    )
    support_result = await session.execute(support_query)
    support_messages = support_result.scalar() or 0

    return {
        'total': total_messages,
        'user': user_messages,
        'support': support_messages,
        'support_percent': round((support_messages / total_messages * 100) if total_messages > 0 else 0, 2)
    }


# Получение детальной статистики по дням
async def get_daily_stats(session: AsyncSession, start_date: datetime, end_date: datetime):

    # Группируем сообщения по дням
    query = text("""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as total_messages,
            COUNT(CASE WHEN sender_type = 'user' THEN 1 END) as user_messages,
            COUNT(CASE WHEN sender_type = 'support' THEN 1 END) as support_messages
        FROM ticket_messages
        WHERE created_at BETWEEN :start_date AND :end_date
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at) DESC
    """)

    result = await session.execute(query, {
        'start_date': start_date,
        'end_date': end_date
    })

    daily_data = []
    for row in result:
        daily_data.append({
            'date': row[0].strftime('%Y-%m-%d'),
            'total_messages': row[1],
            'user_messages': row[2],
            'support_messages': row[3]
        })

    return daily_data


# Получение топ пользователей по количеству сообщений
async def get_top_users(session: AsyncSession, start_date: datetime, end_date: datetime, limit: int = 10):

    query = text("""
        SELECT 
            tm.sender_id,
            t.user_firstname,
            t.user_lastname,
            COUNT(*) as message_count,
            COUNT(DISTINCT tm.ticket_id) as ticket_count
        FROM ticket_messages tm
        LEFT JOIN tickets t ON tm.ticket_id = t.id
        WHERE tm.sender_type = 'user'
            AND tm.created_at BETWEEN :start_date AND :end_date
        GROUP BY tm.sender_id, t.user_firstname, t.user_lastname
        ORDER BY message_count DESC
        LIMIT :limit
    """)

    result = await session.execute(query, {
        'start_date': start_date,
        'end_date': end_date,
        'limit': limit
    })

    top_users = []
    for row in result:
        full_name = f"{row[1] or ''} {row[2] or ''}".strip() or f"User {row[0]}"
        top_users.append({
            'user_id': row[0],
            'name': full_name,
            'message_count': row[3],
            'ticket_count': row[4]
        })

    return top_users


# Вычисление среднего времени ответа саппорта
async def get_avg_response_time(session: AsyncSession, start_date: datetime, end_date: datetime):

    # Сложный запрос для вычисления среднего времени между сообщением пользователя и ответом саппорта
    query = text("""
        WITH user_messages AS (
            SELECT 
                ticket_id,
                created_at,
                ROW_NUMBER() OVER (PARTITION BY ticket_id ORDER BY created_at) as rn
            FROM ticket_messages
            WHERE sender_type = 'user'
                AND created_at BETWEEN :start_date AND :end_date
        ),
        support_messages AS (
            SELECT 
                ticket_id,
                created_at,
                ROW_NUMBER() OVER (PARTITION BY ticket_id ORDER BY created_at) as rn
            FROM ticket_messages
            WHERE sender_type = 'support'
                AND created_at BETWEEN :start_date AND :end_date
        )
        SELECT 
            AVG(EXTRACT(EPOCH FROM (s.created_at - u.created_at))) as avg_response_seconds
        FROM user_messages u
        JOIN support_messages s ON u.ticket_id = s.ticket_id AND u.rn = s.rn
        WHERE s.created_at > u.created_at
    """)

    result = await session.execute(query, {
        'start_date': start_date,
        'end_date': end_date
    })

    avg_seconds = result.scalar()

    if avg_seconds:
        avg_minutes = avg_seconds / 60
        if avg_minutes < 1:
            return f"{int(avg_seconds)} сек"
        elif avg_minutes < 60:
            return f"{int(avg_minutes)} мин"
        else:
            hours = int(avg_minutes // 60)
            minutes = int(avg_minutes % 60)
            return f"{hours} ч {minutes} мин"
    else:
        return "Нет данных"


# CSV файл со всей статистикой
def generate_csv_report(tickets_stats, messages_stats, daily_stats, top_users, avg_response_time, start_date, end_date):

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

    # Заголовок отчета
    writer.writerow(['ОТЧЕТ ПО СТАТИСТИКЕ ТИКЕТОВ'])
    writer.writerow([f'Период: с {start_date.strftime("%d.%m.%Y")} по {end_date.strftime("%d.%m.%Y")}'])
    writer.writerow([])

    # Общая статистика по тикетам
    writer.writerow(['1. ОБЩАЯ СТАТИСТИКА ПО ТИКЕТАМ'])
    writer.writerow(['Всего тикетов', tickets_stats['total']])
    writer.writerow(['Создано за период', tickets_stats['created']])
    writer.writerow(['Закрыто тикетов', tickets_stats['closed']])
    writer.writerow(['Открыто тикетов', tickets_stats['open']])
    writer.writerow(['Процент закрытых', f"{tickets_stats['closed_percent']}%"])
    writer.writerow([])

    # Статистика по сообщениям
    writer.writerow(['2. СТАТИСТИКА ПО СООБЩЕНИЯМ'])
    writer.writerow(['Всего сообщений', messages_stats['total']])
    writer.writerow(['От пользователей', messages_stats['user']])
    writer.writerow(['От саппорта', messages_stats['support']])
    writer.writerow(['Доля саппорта', f"{messages_stats['support_percent']}%"])
    writer.writerow([])

    # Среднее время ответа
    writer.writerow(['3. СРЕДНЕЕ ВРЕМЯ ОТВЕТА'])
    writer.writerow(['Среднее время ответа саппорта', avg_response_time])
    writer.writerow([])

    # Детальная статистика по дням
    if daily_stats:
        writer.writerow(['4. ДЕТАЛЬНАЯ СТАТИСТИКА ПО ДНЯМ'])
        writer.writerow(['Дата', 'Всего сообщений', 'От пользователей', 'От саппорта'])
        for day in daily_stats:
            writer.writerow([
                day['date'],
                day['total_messages'],
                day['user_messages'],
                day['support_messages']
            ])
        writer.writerow([])

    # Топ активных пользователей
    if top_users:
        writer.writerow(['5. ТОП АКТИВНЫХ ПОЛЬЗОВАТЕЛЕЙ'])
        writer.writerow(['ID пользователя', 'Имя', 'Сообщений', 'Тикетов'])
        for user in top_users:
            writer.writerow([
                user['user_id'],
                user['name'],
                user['message_count'],
                user['ticket_count']
            ])

    return output.getvalue()

# Отправка CSV файла пользователю
async def send_csv_file(message: Message, csv_data: str, start_date: datetime, end_date: datetime):

    # Создаем имя файла с датами
    filename = f"stats_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"

    # Конвертируем строку в байты
    csv_bytes = csv_data.encode('utf-8-sig')  # UTF-8 с BOM для Excel

    # Создаем BufferedInputFile
    file = BufferedInputFile(csv_bytes, filename=filename)

    # Отправляем файл
    await message.reply_document(
        document=file,
        caption=f"Статистика за период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
    )


# --------------------------------------------------------------------
# ДОПОЛНИТЕЛЬНАЯ КОМАНДА /stats_advanced (РАСШИРЕННАЯ СТАТИСТИКА)
# --------------------------------------------------------------------
# Расширенная статистика с графиками (если есть pandas и matplotlib)
@stats_router.message(Command("stats_advanced"), F.chat.is_forum == True)
async def handle_stats_advanced_command(message: Message, session: AsyncSession, bot: Bot):
    # Проверка прав администратора
    try:
        chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if chat_member.status not in ['administrator', 'creator']:
            await message.reply("Эта команда доступна только администраторам.")
            return
    except Exception as e:
        logging.error(f"Ошибка проверки прав администратора: {e}")
        await message.reply("Не удалось проверить ваши права.")
        return

    await message.reply("Эта функция в разработке. Используйте /stats для базовой статистики.")


# --------------------------------------------------------------------
# КОМАНДА /stats_user (ДЛЯ ПРОВЕРКИ СТАТИСТИКИ ПОЛЬЗОВАТЕЛЯ)
# --------------------------------------------------------------------
# Показывает статистику по конкретному пользователю (reply на его сообщение)
@stats_router.message(Command("stats_user"), F.chat.is_forum == True)
async def handle_stats_user_command(message: Message, session: AsyncSession, bot: Bot):
    # Проверка прав администратора
    try:
        chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if chat_member.status not in ['administrator', 'creator']:
            await message.reply("Эта команда доступна только администраторам.")
            return
    except Exception as e:
        logging.error(f"Ошибка проверки прав администратора: {e}")
        await message.reply("Не удалось проверить ваши права.")
        return

    # Проверяем, есть ли ответ на сообщение
    if not message.reply_to_message:
        await message.reply("ℹОтветьте на сообщение пользователя, чтобы посмотреть его статистику.")
        return

    user_id = message.reply_to_message.from_user.id
    user_name = message.reply_to_message.from_user.full_name

    # Получаем статистику пользователя
    query = text("""
        SELECT 
            COUNT(DISTINCT tm.ticket_id) as ticket_count,
            COUNT(*) as message_count,
            COUNT(CASE WHEN tm.sender_type = 'user' THEN 1 END) as user_messages,
            COUNT(CASE WHEN tm.sender_type = 'support' THEN 1 END) as support_messages,
            MIN(tm.created_at) as first_message,
            MAX(tm.created_at) as last_message
        FROM ticket_messages tm
        WHERE tm.sender_id = :user_id
    """)

    result = await session.execute(query, {'user_id': user_id})
    row = result.first()

    if row and row[1] > 0:  # Если есть сообщения
        stats_text = f"""
<b>Статистика пользователя: {user_name}</b>
└ ID: <code>{user_id}</code>

<b>Активность:</b>
├ Всего тикетов: {row[0] or 0}
├ Всего сообщений: {row[1] or 0}
├ От пользователя: {row[2] or 0}
└ От саппорта: {row[3] or 0}

<b>Период активности:</b>
├ Первое сообщение: {row[4].strftime('%d.%m.%Y %H:%M') if row[4] else 'Нет данных'}
└ Последнее сообщение: {row[5].strftime('%d.%m.%Y %H:%M') if row[5] else 'Нет данных'}
        """
        await message.reply(stats_text)
    else:
        await message.reply(f"У пользователя {user_name} нет сообщений в системе.")