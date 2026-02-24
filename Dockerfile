FROM python:3.11-slim

ENV POETRY_VERSION=1.8.4 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock* README.md ./
COPY chat_guardian ./chat_guardian
COPY tests ./tests

RUN poetry install --without dev --no-root
RUN poetry install --without dev

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "chat_guardian.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
