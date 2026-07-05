"""storage retention indexes

Revision ID: 20260705_01
Revises: 20260318_01
Create Date: 2026-07-05 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260705_01"
down_revision = "20260318_01"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    chat_columns = _column_names("chat_messages")
    if chat_columns and "message_id" not in chat_columns:
        op.add_column("chat_messages", sa.Column("message_id", sa.String(length=128), nullable=True))
        op.create_index("ix_chat_messages_message_id", "chat_messages", ["message_id"])
    if chat_columns and "message_timestamp" not in chat_columns:
        op.add_column("chat_messages", sa.Column("message_timestamp", sa.DateTime(), nullable=True))
        op.create_index("ix_chat_messages_message_timestamp", "chat_messages", ["message_timestamp"])


def downgrade() -> None:
    chat_columns = _column_names("chat_messages")
    if "message_timestamp" in chat_columns:
        with op.batch_alter_table("chat_messages") as batch_op:
            batch_op.drop_index("ix_chat_messages_message_timestamp")
            batch_op.drop_column("message_timestamp")
    chat_columns = _column_names("chat_messages")
    if "message_id" in chat_columns:
        with op.batch_alter_table("chat_messages") as batch_op:
            batch_op.drop_index("ix_chat_messages_message_id")
            batch_op.drop_column("message_id")
