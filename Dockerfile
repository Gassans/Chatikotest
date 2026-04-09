FROM python:3.10-slim

# Устанавливаем только самое необходимое для работы сети
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Обновляем pip и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем проект
COPY . .

# Запуск через main.py
CMD ["python", "main.py"]
