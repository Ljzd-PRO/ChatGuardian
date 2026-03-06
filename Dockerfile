FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps
COPY frontend .
# Use root-relative base so the built SPA calls backend at /api without double-prefixing.
ENV VITE_API_BASE_URL=/
RUN npm run build

FROM python:3.11-slim AS runtime

ENV POETRY_VERSION=2.3.2 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --without dev --no-root

COPY chat_guardian ./chat_guardian
COPY tests ./tests
COPY --from=frontend-builder /frontend/dist ./frontend/dist

RUN poetry install --without dev

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/health || exit 1

CMD ["poetry", "run", "uvicorn", "chat_guardian.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
