FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Dejamos que Gunicorn use la variable de entorno PORT que da Render
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 60 main:app