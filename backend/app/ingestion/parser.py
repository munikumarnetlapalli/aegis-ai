"""Document parser — converts raw file bytes into structured page text.

Supported formats (M2): PDF, DOCX, HTML, TXT.
Primary parser for PDF:  pypdf  (pure-Python, no neural models).
Primary parser for DOCX: python-docx (pure-Python, no neural models).
Fallback for HTML: BeautifulSoup4.
Fallback for TXT: plain decode.

Why not Docling for the ingestion pipeline?
  Docling's standard PDF pipeline includes a layout detection model that calls
  torch.compile() at inference time. torch.compile JIT-compiles C++ kernels,
  which requires g++ at runtime. The slim container image does not include g++,
  and installing it would add ~300 MB to the image. For text-native regulated
  documents (the primary AegisAI use case), pypdf's text extraction is
  sufficient and requires no system dependencies.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field

from app.ingestion.normalizer import detect_and_decode, normalize_unicode_text

logger = logging.getLogger(__name__)


@dataclass
class ParsedPage:
    """A single parsed page (or logical section) from a document."""

    page_num: int
    text: str
    section_hint: str = ""  # heading or section title if detectable


@dataclass
class ParseResult:
    """The complete output of the parser for one document."""

    pages: list[ParsedPage] = field(default_factory=list)
    page_count: int = 0

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())


# ── Parser dispatch ────────────────────────────────────────────────────────────

class DocumentParser:
    """Parses a document from raw bytes into a list of ParsedPage objects."""

    def parse(
        self,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> ParseResult:
        """Parse document bytes.  Dispatches to the appropriate sub-parser."""
        ext = self._extension(filename)
        logger.info("Parsing %r (ext=%s, size=%d bytes)", filename, ext, len(content))

        if ext in (".pdf",):
            return self._parse_pdf(content, filename)
        elif ext in (".docx",):
            return self._parse_docx(content, filename)
        elif ext in (".html", ".htm"):
            return self._parse_html(content)
        elif ext in (".txt",):
            return self._parse_txt(content)
        else:
            raise ValueError(f"Unsupported file extension: {ext!r}")

    # ── PDF (pypdf — pure Python, no neural models) ───────────────────────────

    def _parse_pdf(self, content: bytes, filename: str) -> ParseResult:
        """Extract text from a text-native PDF using pypdf.

        pypdf operates purely on the PDF content stream — no images, no OCR,
        no PyTorch.  Returns one ParsedPage per PDF page with normalized UTF-8.
        """
        try:
            from pypdf import PdfReader  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "pypdf is required for PDF parsing. "
                "Install it with: pip install pypdf"
            ) from exc

        reader = PdfReader(io.BytesIO(content))
        pages: list[ParsedPage] = []

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = normalize_unicode_text(text).strip()
            if text:
                pages.append(
                    ParsedPage(
                        page_num=page_num + 1,
                        text=text,
                        section_hint="",
                    )
                )

        if not pages:
            logger.warning("pypdf produced no text for %r — may be a scanned PDF", filename)

        logger.info("PDF %r: %d pages extracted", filename, len(pages))
        return ParseResult(pages=pages, page_count=len(pages))

    # ── DOCX (python-docx — pure Python) ──────────────────────────────────────

    def _parse_docx(self, content: bytes, filename: str) -> ParseResult:
        """Extract text from a DOCX file using python-docx.

        Groups paragraphs into logical pages of ~50 paragraphs each.
        Headings are used as section hints. All text is normalized UTF-8.
        """
        try:
            from docx import Document as DocxDocument  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "python-docx is required for DOCX parsing. "
                "Install it with: pip install python-docx"
            ) from exc

        doc = DocxDocument(io.BytesIO(content))
        paragraphs: list[tuple[str, str]] = []  # (text, section_hint)
        current_section = ""

        for para in doc.paragraphs:
            text = normalize_unicode_text(para.text).strip()
            if not text:
                continue
            style_name = (para.style.name or "").lower()
            if "heading" in style_name:
                current_section = text
            paragraphs.append((text, current_section))

        if not paragraphs:
            logger.warning("python-docx produced no content for %r", filename)
            return ParseResult(pages=[], page_count=0)

        # Group ~50 paragraphs per logical "page"
        group_size = 50
        pages: list[ParsedPage] = []
        for i in range(0, len(paragraphs), group_size):
            group = paragraphs[i : i + group_size]
            combined = "\n\n".join(t for t, _ in group)
            section = next((s for _, s in group if s), "")
            pages.append(
                ParsedPage(
                    page_num=i // group_size,
                    text=combined,
                    section_hint=normalize_unicode_text(section),
                )
            )

        logger.info("DOCX %r: %d logical pages extracted", filename, len(pages))
        return ParseResult(pages=pages, page_count=len(pages))

    # ── HTML ──────────────────────────────────────────────────────────────────

    def _parse_html(self, content: bytes) -> ParseResult:
        try:
            from bs4 import BeautifulSoup  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "BeautifulSoup4 is required for HTML parsing.  "
                "Install it with: pip install beautifulsoup4"
            ) from exc

        soup = BeautifulSoup(content, "html.parser")
        # Remove script and style tags
        for tag in soup(["script", "style", "nav", "footer", "head"]):
            tag.decompose()

        pages: list[ParsedPage] = []
        # Split on <h1>/<h2> headings to get logical sections
        sections: list[tuple[str, str]] = []
        current_heading = ""
        current_texts: list[str] = []

        for element in soup.find_all(True):
            if element.name in ("h1", "h2", "h3"):
                if current_texts:
                    sections.append((current_heading, " ".join(current_texts)))
                    current_texts = []
                current_heading = normalize_unicode_text(element.get_text(strip=True))
            elif element.name in ("p", "li", "td", "th"):
                text = normalize_unicode_text(element.get_text(strip=True))
                if text:
                    current_texts.append(text)

        if current_texts:
            sections.append((current_heading, " ".join(current_texts)))

        if not sections:
            # Last resort: dump all text
            sections = [("", normalize_unicode_text(soup.get_text(separator="\n", strip=True)))]

        for i, (heading, text) in enumerate(sections):
            if text.strip():
                pages.append(
                    ParsedPage(
                        page_num=i,
                        text=normalize_unicode_text(text),
                        section_hint=normalize_unicode_text(heading),
                    )
                )

        return ParseResult(pages=pages, page_count=len(pages))

    # ── Plain text ────────────────────────────────────────────────────────────

    def _parse_txt(self, content: bytes) -> ParseResult:
        decoded_text = detect_and_decode(content)
        text = normalize_unicode_text(decoded_text)
        # Split on blank lines to get rough paragraphs, then group into pages
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return ParseResult(pages=[], page_count=0)

        # Group ~50 paragraphs per "page" to keep page numbers meaningful
        chunk_size = 50
        pages: list[ParsedPage] = []
        for i in range(0, len(paragraphs), chunk_size):
            group = paragraphs[i : i + chunk_size]
            pages.append(
                ParsedPage(
                    page_num=i // chunk_size,
                    text="\n\n".join(group),
                    section_hint="",
                )
            )

        return ParseResult(pages=pages, page_count=len(pages))

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extension(filename: str) -> str:
        import os  # noqa: PLC0415

        return os.path.splitext(filename.lower())[1]
