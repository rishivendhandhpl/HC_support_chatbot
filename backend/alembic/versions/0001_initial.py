"""initial schema: pgvector extension + knowledge_chunks + conversation_turns

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("embedding", Vector(_DIM), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("section", sa.String(length=255), nullable=False),
        sa.Column("question", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("pro_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_file", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_knowledge_chunks_pro_only", "knowledge_chunks", ["pro_only"])

    op.create_table(
        "conversation_turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_pro", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("customer_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_conversation_turns_session_id", "conversation_turns", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_turns_session_id", table_name="conversation_turns")
    op.drop_table("conversation_turns")
    op.drop_index("ix_knowledge_chunks_pro_only", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
