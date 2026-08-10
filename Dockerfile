FROM python:3.12-slim

WORKDIR /app

# Install system deps needed by psycopg binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (slim deploy set)
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

# Copy application code
COPY . .

# Render sets PORT env var; default to 8000 for local docker run
ENV PORT=8000

EXPOSE $PORT

CMD uvicorn orchestrator.api:app --host 0.0.0.0 --port $PORT
