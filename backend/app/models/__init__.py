"""ORM models package.

Import all models here so that Alembic's env.py can discover them via
Base.metadata when running migrations.  Order matters — parent tables
(documents) must be imported before child tables (chunks).
"""
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.user import User
from app.models.trace import PipelineTraceModel

__all__ = ["Document", "Chunk", "User", "PipelineTraceModel"]


