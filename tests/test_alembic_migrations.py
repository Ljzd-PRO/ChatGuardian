import sqlite3
from pathlib import Path

from sqlalchemy import inspect, text

from chat_guardian.repositories import _RepositoryDatabase


def _create_legacy_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE detection_results
            (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id            VARCHAR(128),
                generated_at       DATETIME,
                triggered          BOOLEAN,
                trigger_suppressed BOOLEAN,
                payload_json       TEXT
            );
            CREATE TABLE agent_messages
            (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      VARCHAR(64),
                role            VARCHAR(16),
                content         TEXT,
                tool_calls_json TEXT,
                elapsed_ms      INTEGER,
                created_at      VARCHAR(32)
            );
            INSERT INTO detection_results(rule_id, generated_at, triggered, trigger_suppressed, payload_json)
            VALUES ('rule-1', '2026-01-01 00:00:00', 1, 0, '{"result_id":"legacy-result"}');
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_repository_init_runs_alembic_migrations_for_legacy_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite"
    _create_legacy_schema(db_path)

    db = _RepositoryDatabase(f"sqlite:///{db_path}")

    with db.engine.connect() as conn:
        inspector = inspect(conn)
        detection_columns = {col["name"] for col in inspector.get_columns("detection_results")}
        agent_columns = {col["name"] for col in inspector.get_columns("agent_messages")}

        assert "result_id" in detection_columns
        assert "total_tokens" in agent_columns

        result_id = conn.execute(text("SELECT result_id FROM detection_results WHERE id = 1")).scalar_one()
        assert result_id == "legacy-result"

        alembic_version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert alembic_version == "20260318_01"
