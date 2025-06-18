FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    curl \
    libmagic1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

RUN adduser --disabled-password --no-create-home appuser
USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "app.py"]