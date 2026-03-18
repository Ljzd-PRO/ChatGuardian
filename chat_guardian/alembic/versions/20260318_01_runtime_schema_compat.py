"""runtime schema compatibility

Revision ID: 20260318_01
Revises:
Create Date: 2026-03-18 01:00:00
"""

from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260318_01"
down_revision = None
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _try_execute(statements: Iterable[str]) -> None:
    bind = op.get_bind()
    for statement in statements:
        try:
            bind.execute(sa.text(statement))
        except Exception:
            # Keep migration idempotent across SQLite dialect/runtime combinations.
            return


def upgrade() -> None:
    detection_columns = _column_names("detection_results")
    if detection_columns and "result_id" not in detection_columns:
        op.add_column("detection_results", sa.Column("result_id", sa.String(length=128), nullable=True))

    detection_columns = _column_names("detection_results")
    if "result_id" in detection_columns:
        _try_execute(
            [
                "UPDATE detection_results "
                "SET result_id = json_extract(payload_json, '$.result_id') "
                "WHERE result_id IS NULL"
            ]
        )

    agent_columns = _column_names("agent_messages")
    if agent_columns and "total_tokens" not in agent_columns:
        op.add_column("agent_messages", sa.Column("total_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    detection_columns = _column_names("detection_results")
    if "result_id" in detection_columns:
        op.drop_column("detection_results", "result_id")

    agent_columns = _column_names("agent_messages")
    if "total_tokens" in agent_columns:
        op.drop_column("agent_messages", "total_tokens")
