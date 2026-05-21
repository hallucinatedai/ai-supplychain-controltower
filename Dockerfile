# ---------- build stage ----------
FROM python:3.11.9-alpine3.20@sha256:43547ccd3cafdff532797cb4927e5e2b1b4fdb1204bfb0b06ae4e488cceb5ce5 AS builder

WORKDIR /build

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir --prefix=/install .

# ---------- runtime stage ----------
FROM python:3.11.9-alpine3.20@sha256:43547ccd3cafdff532797cb4927e5e2b1b4fdb1204bfb0b06ae4e488cceb5ce5

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=appuser:appuser src/ ./src/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1

CMD ["uvicorn", "controltower.api:app", "--host", "0.0.0.0", "--port", "8000"]
