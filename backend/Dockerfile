# Backend image for Railway (or any Docker host). One process, one uvicorn worker:
# the WebSocket connection manager lives in memory (PLAN section 3).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Runs as root: Railway mounts volumes owned by root, and the app writes to /data.
EXPOSE 8000

# 1. Idempotent seed: fills an empty volume on first boot, changes nothing afterwards.
#    Never --reset here: that would wipe real data on every redeploy.
# 2. Then the API. $PORT comes from the host (Railway sets it); 8000 locally.
CMD ["sh", "-c", "python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
