# Файл: app/models/models.py
from sqlalchemy import BigInteger, String, ForeignKey, Text, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from .base import Base


# Модель для таблицы тикетов (обращений)
class Ticket(Base):
    __tablename__ = 'tickets'  # Название таблицы в БД

    # Колонки таблицы
    id: Mapped[int] = mapped_column(primary_key=True)  # Уникальный ID записи, первичный ключ
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)  # Telegram ID пользователя
    user_firstname: Mapped[str] = mapped_column(String(128))  # Имя пользователя
    user_lastname: Mapped[str | None] = mapped_column(String(128))  # Фамилия (может отсутствовать)
    topic_id: Mapped[int] = mapped_column(BigInteger)  # ID темы в группе поддержки
    status: Mapped[str] = mapped_column(String(50), default='open')  # Статус тикета ('open', 'closed')

    # Связь с сообщениями
    messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",  # При удалении тикета удаляются и сообщения
        foreign_keys="[TicketMessage.ticket_id]"
    )


# Модель для таблицы сообщений тикетов
class TicketMessage(Base):
    __tablename__ = 'ticket_messages'  # Название таблицы в БД (изменено на более понятное)

    # Колонки таблицы
    id: Mapped[int] = mapped_column(primary_key=True)  # Уникальный ID записи, первичный ключ
    ticket_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('tickets.id', ondelete='CASCADE'),  # Внешний ключ на tickets.id
        nullable=False
    )  # Связь с тикетом
    sender_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='user'
    )  # Кто написал: 'user' или 'support'
    sender_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Telegram ID написавшего
    message_text: Mapped[str] = mapped_column(Text, nullable=False)  # Текст сообщения (с пометками [PHOTO] и т.д.)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Связь с моделью Ticket (для удобной навигации)
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="messages", foreign_keys=[ticket_id])
