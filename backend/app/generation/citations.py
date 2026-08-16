"""Citation validator — prevents hallucinated citations.

Design rule (non-negotiable):
    The model must NEVER invent a citation identifier.
    Every citation returned to the client must resolve to a chunk that was
    actually retrieved and passed into the generation context for this request.

This module:
1. Parses [N] markers from the LLM response text.
2. Resolves each marker to its corresponding chunk via a citation map built
   from the retrieved chunks.
3. Rejects any marker that does not resolve to a retrieved chunk.
4. Returns structured Citation objects.

The citation map is constructed from the ordered list of retrieved chunks
passed to the LLM prompt.  Chunk [1] is the first chunk in context, [2] the
second, etc.  The LLM is instructed to use these numbers exclusively.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass

from app.retrieval.service import RetrievalResult

logger = logging.getLogger(__name__)

# Matches citation markers like [1], [2], [12]
_CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclass
class Citation:
    """A validated, resolved citation pointing to a real retrieved chunk."""

    citation_number: int
    chunk_id: uuid.UUID
    filename: str
    section: str
    page: int
    excerpt: str  # First 200 chars of the chunk content


def validate_citations(
    response_text: str,
    context_chunks: list[RetrievalResult],
) -> tuple[str, list[Citation]]:
    """Parse and validate [N] citation markers in an LLM response.

    Parameters
    ----------
    response_text : str
        Raw text from the LLM that may contain [N] markers.
    context_chunks : list[RetrievalResult]
        The chunks that were passed to the LLM as context, in order.
        Citation [1] maps to context_chunks[0], [2] to context_chunks[1], etc.

    Returns
    -------
    (cleaned_text, citations)
        cleaned_text: response with invalid markers stripped
        citations: validated Citation objects (deduplicated, sorted by number)
    """
    # Build citation map: number (1-indexed) → RetrievalResult
    citation_map: dict[int, RetrievalResult] = {
        i + 1: chunk for i, chunk in enumerate(context_chunks)
    }

    # Find all [N] markers in the response
    cited_numbers = set(int(m) for m in _CITATION_RE.findall(response_text))

    # Validate: keep only markers that resolve to an actual context chunk
    valid_numbers: set[int] = set()
    invalid_numbers: set[int] = set()
    for n in cited_numbers:
        if n in citation_map:
            valid_numbers.add(n)
        else:
            invalid_numbers.add(n)
            logger.warning(
                "Citation [%d] rejected — not in retrieved context (context size=%d)",
                n,
                len(context_chunks),
            )

    # Strip invalid markers from the response text
    cleaned_text = response_text
    for n in invalid_numbers:
        cleaned_text = cleaned_text.replace(f"[{n}]", "")

    # Build Citation objects for valid markers (deduplicated, sorted)
    citations: list[Citation] = []
    seen: set[int] = set()
    for n in sorted(valid_numbers):
        if n in seen:
            continue
        seen.add(n)
        chunk = citation_map[n]
        citations.append(
            Citation(
                citation_number=n,
                chunk_id=chunk.chunk_id,
                filename=chunk.provenance.filename,
                section=chunk.provenance.section,
                page=chunk.provenance.page,
                excerpt=chunk.content[:200].strip(),
            )
        )

    logger.info(
        "Citations: %d markers found, %d valid, %d rejected",
        len(cited_numbers),
        len(valid_numbers),
        len(invalid_numbers),
    )
    return cleaned_text.strip(), citations
