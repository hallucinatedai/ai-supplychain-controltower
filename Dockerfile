# ---------- build stage ----------
FROM python:3.11-alpine3.21@sha256:cc89153ee2e125296614f6a032cb473e2bc2c0203cbe2305c917ece8866e5b01 AS builder

WORKDIR /build

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir --prefix=/install .

# ---------- runtime stage ----------
FROM python:3.11-alpine3.21@sha256:cc89153ee2e125296614f6a032cb473e2bc2c0203cbe2305c917ece8866e5b01

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=appuser:appuser src/ ./src/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1

CMD ["uvicorn", "controltower.api:app", "--host", "0.0.0.0", "--port", "8000"]
