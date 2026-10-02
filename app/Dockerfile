FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd \
      --system \
      --gid 10001 \
      appgroup \
    && useradd \
      --system \
      --uid 10001 \
      --gid appgroup \
      --no-create-home \
      appuser \
    && mkdir -p /var/log/demo-api \
    && chown -R appuser:appgroup /var/log/demo-api

COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    -r requirements.txt

COPY --chown=appuser:appgroup main.py .

USER 10001:10001

EXPOSE 8000

HEALTHCHECK \
  --interval=10s \
  --timeout=3s \
  --start-period=10s \
  --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]