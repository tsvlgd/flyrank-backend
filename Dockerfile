# Stage 1: Build & Dependency Installation
FROM python:3.12-slim AS builder

# Install uv globally
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: Final Light Runtime Image
FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY . .


CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]

