FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEMO_MODE=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY data/*.csv data/*.json ./data/
COPY fixtures ./fixtures
# Готовая сборка UI подключается compose как каталог только для чтения.
EXPOSE 8000
CMD ["python", "-m", "app.cli", "serve", "--host", "0.0.0.0"]
