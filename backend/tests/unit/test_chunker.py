"""Unit tests for the Chunker.

Tests the chunking logic in isolation — no database, no embeddings.
"""
from __future__ import annotations

import pytest

from app.ingestion.chunker import Chunker, RawChunk
from app.ingestion.parser import ParsedPage


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_chunker(chunk_size: int = 100, chunk_overlap: int = 10) -> Chunker:
    return Chunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def make_page(text: str, page_num: int = 0, section: str = "") -> ParsedPage:
    return ParsedPage(page_num=page_num, text=text, section_hint=section)


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestChunkerInit:
    def test_valid_init(self):
        c = make_chunker(100, 10)
        assert c.chunk_size == 100
        assert c.chunk_overlap == 10

    def test_overlap_equal_to_size_raises(self):
        with pytest.raises(ValueError, match="chunk_overlap"):
            Chunker(chunk_size=50, chunk_overlap=50)

    def test_overlap_greater_than_size_raises(self):
        with pytest.raises(ValueError):
            Chunker(chunk_size=50, chunk_overlap=60)


class TestChunkerEmptyInput:
    def test_empty_pages_list(self):
        c = make_chunker()
        assert c.chunk_pages([]) == []

    def test_page_with_empty_text(self):
        c = make_chunker()
        pages = [make_page("")]
        result = c.chunk_pages(pages)
        assert result == []

    def test_page_with_whitespace_only(self):
        c = make_chunker()
        pages = [make_page("   \n   \n   ")]
        result = c.chunk_pages(pages)
        assert result == []


class TestChunkerBasic:
    def test_single_short_paragraph(self):
        """A paragraph shorter than chunk_size should be one chunk."""
        c = make_chunker(chunk_size=200, chunk_overlap=20)
        text = "This is a short paragraph."
        pages = [make_page(text, page_num=1, section="Intro")]
        chunks = c.chunk_pages(pages)

        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].page == 1
        assert chunks[0].section == "Intro"
        assert chunks[0].chunk_index == 0

    def test_chunk_index_increments(self):
        """chunk_index should be unique and incrementing across the document."""
        c = make_chunker(chunk_size=10, chunk_overlap=2)
        # Create text that will produce multiple chunks
        text = "\n\n".join([f"Paragraph {i}. " * 5 for i in range(10)])
        pages = [make_page(text)]
        chunks = c.chunk_pages(pages)

        indices = [ch.chunk_index for ch in chunks]
        assert indices == list(range(len(chunks))), "Indices must be contiguous"

    def test_multiple_pages_preserve_page_number(self):
        """Each chunk must carry the page number of the page it came from."""
        c = make_chunker(chunk_size=200, chunk_overlap=20)
        pages = [
            make_page("Page zero content here.", page_num=0),
            make_page("Page one content here.", page_num=1),
        ]
        chunks = c.chunk_pages(pages)
        page_nums = {ch.page for ch in chunks}
        assert 0 in page_nums
        assert 1 in page_nums

    def test_output_types(self):
        c = make_chunker()
        pages = [make_page("Hello world. " * 5)]
        chunks = c.chunk_pages(pages)
        for ch in chunks:
            assert isinstance(ch, RawChunk)
            assert isinstance(ch.content, str)
            assert isinstance(ch.page, int)
            assert isinstance(ch.section, str)
            assert isinstance(ch.chunk_index, int)


class TestChunkerSizeConstraints:
    def test_chunks_respect_approximate_size(self):
        """No chunk should be dramatically larger than the target in characters."""
        c = make_chunker(chunk_size=50, chunk_overlap=5)
        # 50 tokens * 4 chars/token = 200 chars target
        # Allow 2x as a generous bound (paragraph boundary rounding)
        max_chars = 50 * c._CHARS_PER_TOKEN * 2

        long_text = "Word " * 500
        pages = [make_page(long_text)]
        chunks = c.chunk_pages(pages)

        assert len(chunks) > 1, "Long text should produce multiple chunks"
        for ch in chunks:
            assert len(ch.content) <= max_chars, (
                f"Chunk too large: {len(ch.content)} chars (max {max_chars})"
            )

    def test_no_empty_chunks(self):
        """Chunker must never produce chunks with empty content."""
        c = make_chunker(chunk_size=30, chunk_overlap=3)
        text = "\n\n".join([f"Para {i}: some content." for i in range(20)])
        pages = [make_page(text)]
        chunks = c.chunk_pages(pages)
        for ch in chunks:
            assert ch.content.strip(), "All chunks must have non-empty content"


class TestChunkerProvenance:
    def test_section_is_preserved(self):
        c = make_chunker(chunk_size=200, chunk_overlap=20)
        pages = [make_page("Content here.", section="§ 8.2 Settlement Period")]
        chunks = c.chunk_pages(pages)
        assert all(ch.section == "§ 8.2 Settlement Period" for ch in chunks)

    def test_global_chunk_index_offset(self):
        """global_offset parameter must shift chunk indices correctly."""
        c = make_chunker(chunk_size=200, chunk_overlap=20)
        pages = [make_page("Short text.")]
        chunks = c.chunk_pages(pages, global_offset=10)
        assert chunks[0].chunk_index == 10
