"""runtime schema compatibility

Revision ID: 20260318_01
Revises:
Create Date: 2026-03-18 01:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260318_01"
down_revision = None
branch_labels = None
depends_on = None

RESULT_ID_LENGTH = 128


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _try_backfill_result_id() -> None:
    bind = op.get_bind()
    try:
        bind.execute(
            sa.text(
                "UPDATE detection_results "
                "SET result_id = json_extract(payload_json, '$.result_id') "
                "WHERE result_id IS NULL"
            )
        )
    except sa.exc.OperationalError:
        # Keep migration compatible with databases that don't provide json_extract.
        return


def upgrade() -> None:
    detection_columns = _column_names("detection_results")
    if detection_columns and "result_id" not in detection_columns:
        op.add_column("detection_results", sa.Column("result_id", sa.String(length=RESULT_ID_LENGTH), nullable=True))

    detection_columns = _column_names("detection_results")
    if "result_id" in detection_columns:
        _try_backfill_result_id()

    agent_columns = _column_names("agent_messages")
    if agent_columns and "total_tokens" not in agent_columns:
        op.add_column("agent_messages", sa.Column("total_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    detection_columns = _column_names("detection_results")
    if "result_id" in detection_columns:
        with op.batch_alter_table("detection_results") as batch_op:
            batch_op.drop_column("result_id")

    agent_columns = _column_names("agent_messages")
    if "total_tokens" in agent_columns:
        with op.batch_alter_table("agent_messages") as batch_op:
            batch_op.drop_column("total_tokens")
