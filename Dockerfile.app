FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM node:22-bookworm-slim AS app-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    gnupg2 \
    lsb-release \
    ca-certificates \
    redis-server \
    && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY rss-gen/requirements.txt ./rss-gen/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt \
    && /opt/venv/bin/pip install -r rss-gen/requirements.txt

FROM app-base AS production
WORKDIR /app
COPY . .
RUN chmod +x /app/scripts/start_app_prod.sh /app/scripts/start_app_dev.sh
WORKDIR /app/frontend
RUN npm install --omit=dev
COPY --from=frontend-builder /app/frontend/build ./build
WORKDIR /app
EXPOSE 3456 8765 3460
CMD ["bash", "/app/scripts/start_app_prod.sh"]

FROM app-base AS development
WORKDIR /app
COPY . .
RUN chmod +x /app/scripts/start_app_prod.sh /app/scripts/start_app_dev.sh
WORKDIR /app/frontend
RUN npm install
WORKDIR /app
EXPOSE 3456 8765 3460
CMD ["bash", "/app/scripts/start_app_dev.sh"]
