FROM python:3.12-slim

# Не писать .pyc, не буферизовать вывод (логи сразу видны в docker logs).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHTODATA_DATA_DIR=/app/data

WORKDIR /app

# Сначала зависимости — лучше кешируется при сборке.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения.
COPY app/ ./app/
COPY scripts/ ./scripts/

# Каталог данных (база собирается на старте; том монтируется снаружи).
RUN mkdir -p /app/data

EXPOSE 8000

# При первом запуске с пустым томом база скачается с opendata.digital.gov.ru
# автоматически (в lifespan приложения), далее обновляется по расписанию.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://127.0.0.1:8000/api/health').json().get('status')=='ok' else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
