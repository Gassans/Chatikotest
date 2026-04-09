FROM python:3.10-slim

# Системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала копируем только requirements.txt, чтобы Docker кэшировал слои
COPY requirements.txt .

# Обновляем pip и устанавливаем всё одной командой
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
# Если chat-downloader нет в requirements.txt, ставим его здесь принудительно
RUN pip install --upgrade chat-downloader nest_asyncio

COPY . .

CMD ["python", "main.py"]
