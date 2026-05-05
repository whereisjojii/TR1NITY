# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------
# TR1NITY · ingestor service
# ---------------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install runtime deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY app ./app

# Drop privileges
RUN useradd --system --uid 10001 --no-create-home tr1nity \
    && chown -R tr1nity:tr1nity /app
USER tr1nity

EXPOSE 8001

# Healthcheck mirrors Compose
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
import json; \
r=urllib.request.urlopen('http://localhost:8001/healthz', timeout=3); \
sys.exit(0 if r.status==200 else 1)" || exit 1

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--proxy-headers", \
     "--no-access-log"]
