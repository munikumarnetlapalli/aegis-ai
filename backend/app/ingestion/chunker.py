"""Structure-aware text chunker.

Chunking strategy (from skill spec):
  - Prefer structure-aware over blind character splitting.
  - Preserve paragraph and section boundaries where possible.
  - Chunk size and overlap are configurable (never hard-coded).
  - Starting point: ~512 tokens, ~10% overlap (≈51 tokens).

Tokenisation: uses a fast whitespace approximation (1 token ≈ 0.75 words)
to avoid a mandatory tiktoken/transformers dependency at import time.
This is intentionally a *starting point* — measure retrieval quality against
the golden set (M6) before tuning these parameters.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingestion.normalizer import normalize_unicode_text


@dataclass
class RawChunk:
    """A single text chunk ready for embedding and indexing."""

    content: str
    page: int
    section: str
    chunk_index: int  # 0-based index within the document


class Chunker:
    """Splits parsed document pages into fixed-size, overlapping text chunks.

    Parameters
    ----------
    chunk_size : int
        Target chunk size in tokens (approximate).
    chunk_overlap : int
        Number of tokens to overlap between consecutive chunks.
    """

    # Rough chars-per-token estimate (whitespace tokenisation).
    # A real tokeniser (tiktoken) would be more accurate but adds a dep.
    _CHARS_PER_TOKEN = 4

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be < chunk_size ({chunk_size})"
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._target_chars = chunk_size * self._CHARS_PER_TOKEN
        self._overlap_chars = chunk_overlap * self._CHARS_PER_TOKEN

    # ── Public API ─────────────────────────────────────────────────────────────

    def chunk_pages(
        self,
        pages: list,  # list[ParsedPage]
        global_offset: int = 0,
    ) -> list[RawChunk]:
        """Chunk a list of ParsedPage objects into RawChunks.

        Paragraph boundaries are respected: we never split mid-paragraph
        unless the paragraph itself exceeds chunk_size.
        """
        chunks: list[RawChunk] = []
        chunk_index = global_offset

        for page in pages:
            page_chunks = self._chunk_text(
                text=page.text,
                page=page.page_num,
                section=page.section_hint,
                start_index=chunk_index,
            )
            chunks.extend(page_chunks)
            chunk_index += len(page_chunks)

        return chunks

    # ── Internal ───────────────────────────────────────────────────────────────

    def _chunk_text(
        self,
        text: str,
        page: int,
        section: str,
        start_index: int,
    ) -> list[RawChunk]:
        """Split a single block of text into overlapping chunks."""
        paragraphs = self._split_paragraphs(text)
        if not paragraphs:
            return []

        chunks: list[RawChunk] = []
        current_parts: list[str] = []
        current_chars = 0
        chunk_index = start_index

        for para in paragraphs:
            para_chars = len(para)

            # If this paragraph alone exceeds the target, split it further.
            if para_chars > self._target_chars:
                # Flush what we have first
                if current_parts:
                    chunks.append(
                        RawChunk(
                            content=normalize_unicode_text(self._join(current_parts)),
                            page=page,
                            section=normalize_unicode_text(section),
                            chunk_index=chunk_index,
                        )
                    )
                    chunk_index += 1
                    current_parts, current_chars = self._carry_overlap(current_parts)

                # Split the long paragraph by sentences
                for sub_chunk in self._split_long(para, page, section, chunk_index):
                    chunks.append(sub_chunk)
                    chunk_index += 1
                continue

            # Would adding this paragraph exceed the limit?
            if current_chars + para_chars > self._target_chars and current_parts:
                chunks.append(
                    RawChunk(
                        content=normalize_unicode_text(self._join(current_parts)),
                        page=page,
                        section=normalize_unicode_text(section),
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1
                current_parts, current_chars = self._carry_overlap(current_parts)

            current_parts.append(para)
            current_chars += para_chars

        # Flush remaining
        if current_parts:
            chunks.append(
                RawChunk(
                    content=normalize_unicode_text(self._join(current_parts)),
                    page=page,
                    section=normalize_unicode_text(section),
                    chunk_index=chunk_index,
                )
            )

        return chunks

    def _split_long(
        self, text: str, page: int, section: str, start_index: int
    ) -> list[RawChunk]:
        """Split a paragraph that is longer than chunk_size by character window."""
        chunks: list[RawChunk] = []
        step = self._target_chars - self._overlap_chars
        if step <= 0:
            step = self._target_chars  # safety fallback

        idx = start_index
        pos = 0
        while pos < len(text):
            end = pos + self._target_chars
            piece = text[pos:end].strip()
            if piece:
                chunks.append(
                    RawChunk(
                        content=normalize_unicode_text(piece),
                        page=page,
                        section=normalize_unicode_text(section),
                        chunk_index=idx,
                    )
                )
                idx += 1
            pos += step

        return chunks

    def _carry_overlap(self, parts: list[str]) -> tuple[list[str], int]:
        """Return the trailing portion of parts to carry as overlap."""
        carried: list[str] = []
        carried_chars = 0
        for part in reversed(parts):
            if carried_chars + len(part) > self._overlap_chars:
                break
            carried.insert(0, part)
            carried_chars += len(part)
        return carried, carried_chars

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """Split text on blank lines and strip each paragraph."""
        parts = re.split(r"\n{2,}", text)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _join(parts: list[str]) -> str:
        return "\n\n".join(parts)
