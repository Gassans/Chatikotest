FROM python:3.10-slim

# Системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# 1. Обновляем pip
RUN pip install --upgrade pip

# 2. Устанавливаем зависимости из файла
RUN pip install --no-cache-dir -r requirements.txt

# 3. ПРИНУДИТЕЛЬНО обновляем chat-downloader до последней версии
RUN pip install --upgrade --no-cache-dir chat-downloader

COPY . .
CMD ["python", "main.py"]
