from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _normalize_sync_url(url: str) -> str:
    """Normalize database URLs for use with Alembic's synchronous engine.

    - Convert `sqlite+aiosqlite://` URLs to `sqlite://` while preserving the rest
      of the URL.
    - Reject other async driver URLs (e.g. `postgresql+asyncpg`) with a clear
      error message, since Alembic uses synchronous SQLAlchemy engines here.
    """
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)

    if scheme == "sqlite+aiosqlite":
        return "sqlite://" + rest

    if "+" in scheme:
        raise RuntimeError(
            f"Unsupported async database URL for Alembic migrations: {url!r}. "
            "Please use a synchronous SQLAlchemy URL (for example, replace "
            "'+aiosqlite' or other async drivers with their synchronous "
            "equivalents)."
        )

    return url


def _configured_url() -> str:
    env_url = os.getenv("CHAT_GUARDIAN_DATABASE_URL")
    if env_url:
        return _normalize_sync_url(env_url)
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return _normalize_sync_url(configured)
    return "sqlite:///./db.sqlite"


def run_migrations_offline() -> None:
    context.configure(
        url=_configured_url(),
        target_metadata=None,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=None, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _configured_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as online_connection:
        context.configure(connection=online_connection, target_metadata=None, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
