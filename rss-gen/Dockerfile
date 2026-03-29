FROM python:3.11-slim

RUN groupadd -r rssgen && useradd -r -g rssgen -d /app rssgen

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY fastapi_backend/ fastapi_backend/

RUN mkdir -p /app/.cache && chown -R rssgen:rssgen /app

USER rssgen

EXPOSE 3460

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3460"]
