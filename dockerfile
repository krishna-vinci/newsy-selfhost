FROM python:3.11-slim

# No system dependencies required for asyncpg

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy your FastAPI application code
COPY . .

# Expose FastAPI port
EXPOSE 8321

# Run your FastAPI app with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8321"]
