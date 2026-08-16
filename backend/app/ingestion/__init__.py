"""Ingestion package."""
from app.ingestion.service import IngestionService
from app.ingestion.embedding import EmbeddingProvider, get_embedding_provider

__all__ = ["IngestionService", "EmbeddingProvider", "get_embedding_provider"]
