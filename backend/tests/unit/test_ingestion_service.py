"""Unit tests for IngestionService.

Uses mocks for the parser, chunker, and embedding provider so these tests
run with no database, no file IO, and no ML models.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingestion.chunker import RawChunk
from app.ingestion.parser import ParsedPage, ParseResult
from app.ingestion.service import IngestionService


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_service() -> IngestionService:
    """Create an IngestionService with a real chunker but mocked-out parser."""
    with patch("app.ingestion.service.DocumentParser") as MockParser:
        MockParser.return_value = MagicMock()
        svc = IngestionService()
    return svc


def make_mock_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    return db


# ── Validation tests ───────────────────────────────────────────────────────────

class TestIngestionValidation:
    def test_rejects_oversized_file(self):
        svc = make_service()
        big = b"x" * (51 * 1024 * 1024)  # 51 MB > 50 MB limit

        from app.core.config import get_settings
        settings = get_settings()

        with pytest.raises(ValueError, match="too large"):
            svc._validate(big, "doc.pdf", settings)

    def test_rejects_unsupported_extension(self):
        svc = make_service()
        from app.core.config import get_settings
        settings = get_settings()

        with pytest.raises(ValueError, match="Unsupported"):
            svc._validate(b"content", "doc.exe", settings)

    def test_accepts_valid_pdf(self):
        svc = make_service()
        from app.core.config import get_settings
        settings = get_settings()
        # Should not raise
        svc._validate(b"content", "policy.pdf", settings)

    def test_accepts_valid_txt(self):
        svc = make_service()
        from app.core.config import get_settings
        settings = get_settings()
        svc._validate(b"content", "readme.txt", settings)

    @pytest.mark.parametrize("ext", [".pdf", ".docx", ".html", ".txt"])
    def test_all_allowed_extensions(self, ext: str):
        svc = make_service()
        from app.core.config import get_settings
        settings = get_settings()
        svc._validate(b"x", f"file{ext}", settings)


# ── Ingestion pipeline tests ───────────────────────────────────────────────────

class TestIngestionService:
    @pytest.mark.asyncio
    async def test_successful_ingestion_sets_indexed_status(self):
        """On success the Document should be marked 'indexed'."""
        svc = make_service()
        db = make_mock_db()

        parse_result = ParseResult(
            pages=[ParsedPage(page_num=0, text="Policy covers flood damage. " * 20)],
            page_count=1,
        )
        svc._parser.parse.return_value = parse_result

        fake_doc = MagicMock()
        fake_doc.id = uuid.uuid4()

        # When db.add is called with a Document, store it
        added_docs = []
        def capture_add(obj):
            added_docs.append(obj)
        db.add.side_effect = capture_add

        with (
            patch("app.ingestion.service.Document", return_value=fake_doc),
            patch("app.ingestion.service.get_embedding_provider") as mock_embed,
        ):
            provider = MagicMock()
            provider.embed_documents.return_value = [[0.1] * 384]
            mock_embed.return_value = provider

            result = await svc.ingest(
                file_bytes=b"dummy content",
                filename="policy.txt",
                content_type="text/plain",
                jurisdiction="EU",
                allowed_roles=["analyst"],
                db=db,
            )

        assert result.status == "indexed"
        assert result.chunk_count > 0
        assert result.filename == "policy.txt"

    @pytest.mark.asyncio
    async def test_all_chunks_have_required_provenance(self):
        """Every Chunk inserted must have non-empty provenance fields."""
        svc = make_service()
        db = make_mock_db()

        parse_result = ParseResult(
            pages=[
                ParsedPage(
                    page_num=2,
                    text="Section 8.2: Settlement period is 30 days. " * 10,
                    section_hint="§ 8.2",
                )
            ],
            page_count=1,
        )
        svc._parser.parse.return_value = parse_result

        fake_doc = MagicMock()
        fake_doc.id = uuid.uuid4()
        inserted_chunks = []

        def capture_add_all(objs):
            inserted_chunks.extend(objs)
        db.add_all.side_effect = capture_add_all

        with (
            patch("app.ingestion.service.Document", return_value=fake_doc),
            patch("app.ingestion.service.get_embedding_provider") as mock_embed,
        ):
            provider = MagicMock()
            provider.embed_documents.side_effect = lambda texts: [[0.0] * 384] * len(texts)
            mock_embed.return_value = provider

            await svc.ingest(
                file_bytes=b"x",
                filename="contract.txt",
                content_type="text/plain",
                jurisdiction="US",
                allowed_roles=["admin"],
                db=db,
            )

        assert len(inserted_chunks) > 0
        for chunk in inserted_chunks:
            assert chunk.document_id == fake_doc.id
            assert chunk.filename == "contract.txt"
            assert chunk.jurisdiction == "US"
            assert "admin" in chunk.allowed_roles
            assert isinstance(chunk.page, int)
            assert isinstance(chunk.chunk_index, int)
            assert chunk.content.strip()

    @pytest.mark.asyncio
    async def test_failed_parse_marks_document_failed(self):
        """If the parser raises, the document should be marked 'failed'."""
        svc = make_service()
        db = make_mock_db()
        svc._parser.parse.side_effect = RuntimeError("Parse error")

        fake_doc = MagicMock()
        fake_doc.id = uuid.uuid4()

        with patch("app.ingestion.service.Document", return_value=fake_doc):
            with pytest.raises(RuntimeError, match="Parse error"):
                await svc.ingest(
                    file_bytes=b"x",
                    filename="broken.txt",
                    content_type="text/plain",
                    jurisdiction="GLOBAL",
                    allowed_roles=[],
                    db=db,
                )

        assert fake_doc.status == "failed"
        assert fake_doc.error_message is not None
