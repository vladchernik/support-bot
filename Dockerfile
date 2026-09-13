# Dockerfile

# Используем легковесный образ Python
FROM python:3.11-slim

# Отключаем буферизацию Python, чтобы логи сразу появлялись в Docker
ENV PYTHONUNBUFFERED=1

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем только файл с зависимостями, чтобы использовать кэш Docker
COPY requirements.txt .

# Обновляем pip и устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код проекта в рабочую директорию
COPY . .

# Команда для запуска нашего бота как модуля
CMD ["python", "-m", "app.main"]