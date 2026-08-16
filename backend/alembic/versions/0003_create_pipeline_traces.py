"""0003 — Create pipeline_traces table for M7 observability.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-15

Installs:
  - pipeline_traces table storing privacy-safe telemetry metrics
  - Indexes on request_id, query_hash, and created_at
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_traces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("user_role", sa.String(64), nullable=True),
        sa.Column("jurisdiction", sa.String(64), nullable=True),
        sa.Column("total_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("retrieval_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("reranker_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("llm_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("top_reranker_score", sa.Float(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("abstained", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("guardrail_blocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_pipeline_traces_request_id", "pipeline_traces", ["request_id"])
    op.create_index("ix_pipeline_traces_query_hash", "pipeline_traces", ["query_hash"])
    op.create_index("ix_pipeline_traces_created_at", "pipeline_traces", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_traces_created_at", table_name="pipeline_traces")
    op.drop_index("ix_pipeline_traces_query_hash", table_name="pipeline_traces")
    op.drop_index("ix_pipeline_traces_request_id", table_name="pipeline_traces")
    op.drop_table("pipeline_traces")
