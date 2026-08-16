"""Unicode and UTF-8 text normalizer for AegisAI.

Ensures that document text, section hints, chunk content, citations, and API responses
maintain clean, uncorrupted UTF-8 text throughout the entire pipeline.

Handles:
1. Decoding raw bytes using multi-encoding detection with fallback (UTF-8, UTF-8-SIG, CP1252, Latin-1, UTF-16).
2. Fixing Private Use Area (PUA) font mappings from PDF symbol fonts (e.g. \\uF8E9 -> ©, \\uF0B7 -> •, \\uF0A7 -> §).
3. Fixing MacRoman/Apple font extraction artifacts (e.g. ï£© -> ©).
4. Fixing Latin-1/CP1252 mojibake (e.g. Â§ -> §, â€™ -> ’, â€” -> —, â€“ -> –, Ã© -> é, etc.).
5. Normalizing text to Unicode NFC canonical composition (unicodedata.normalize('NFC', ...)).
6. Stripping null bytes (\\x00) which cause PostgreSQL string insertion errors.
"""
from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# Common PDF / Symbol font Private Use Area (PUA) mappings to standard Unicode
PUA_SYMBOL_MAP: dict[str, str] = {
    "\uf8e9": "©",  # Adobe/Apple symbol copyright
    "\uf8ea": "®",  # Adobe/Apple symbol registered
    "\uf8eb": "™",  # Adobe/Apple symbol trademark
    "\uf8e7": "®",
    "\uf8e8": "™",
    "\uf0a7": "§",  # Section sign in Symbol font
    "\uf0b7": "•",  # Bullet point in Symbol font
    "\uf020": " ",  # Symbol font space
    "\uf02d": "-",  # Symbol font hyphen/minus
    "\uf06e": "■",  # Symbol font square
    "\uf076": "v",
    "\uf0d8": "→",
    "\uf0e0": "→",
    "\ufb00": "ff",  # Standard ligatures
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "ft",
    "\ufb06": "st",
}

# Known mojibake artifacts from PDF extractions or incorrect Latin-1/CP1252 double decoding
MOJIBAKE_REPLACEMENTS: list[tuple[str, str]] = [
    # PDF specific artifacts
    ("ï£©", "©"),
    ("ï¿½", ""),  # Unicode replacement char artifact
    # Currency and legal symbols
    ("Â§", "§"),
    ("Â©", "©"),
    ("Â®", "®"),
    ("Â°", "°"),
    ("Â±", "±"),
    ("Âµ", "µ"),
    ("Â¶", "¶"),
    ("Â·", "·"),
    ("Â«", "«"),
    ("Â»", "»"),
    ("â„¢", "™"),
    ("â‚¬", "€"),
    ("Â£", "£"),
    ("Â¥", "¥"),
    # Quotes and dashes
    ("â€™", "’"),
    ("â€˜", "‘"),
    ("â€œ", "“"),
    ("â€\x9d", "”"),
    ("â€\x9c", "“"),
    ("â€\x99", "’"),
    ("â€\x98", "‘"),
    ("â€\"", "”"),
    ("â€", "”"),
    ("â€”", "—"),
    ("â€“", "–"),
    ("â€¢", "•"),
    ("â€¦", "…"),
    ("â€¹", "‹"),
    ("â€º", "›"),
    ("â‰¥", "≥"),
    ("â‰¤", "≤"),
    ("â‰ˆ", "≈"),
    ("â‰ ", "≠"),
    ("â†’", "→"),
    ("â†’", "←"),
    # Accented letters (Latin-1 mojibake)
    ("Ã©", "é"),
    ("Ã¨", "è"),
    ("Ã ", "à"),
    ("Ã¡", "á"),
    ("Ã¢", "â"),
    ("Ã¤", "ä"),
    ("Ã£", "ã"),
    ("Ã¥", "å"),
    ("Ã¦", "æ"),
    ("Ã§", "ç"),
    ("Ãª", "ê"),
    ("Ã«", "ë"),
    ("Ã¬", "ì"),
    ("Ã­", "í"),
    ("Ã®", "î"),
    ("Ã¯", "ï"),
    ("Ã°", "ð"),
    ("Ã±", "ñ"),
    ("Ã²", "ò"),
    ("Ã³", "ó"),
    ("Ã´", "ô"),
    ("Ãµ", "õ"),
    ("Ã¶", "ö"),
    ("Ã·", "÷"),
    ("Ã¸", "ø"),
    ("Ã¹", "ù"),
    ("Ãº", "ú"),
    ("Ã»", "û"),
    ("Ã¼", "ü"),
    ("Ã½", "ý"),
    ("Ã¾", "þ"),
    ("Ã¿", "ÿ"),
    ("Ã€", "À"),
    ("Ã", "Á"),
    ("Ã‚", "Â"),
    ("Ãƒ", "Ã"),
    ("Ã„", "Ä"),
    ("Ã…", "Å"),
    ("Ã†", "Æ"),
    ("Ã‡", "Ç"),
    ("Ãˆ", "È"),
    ("Ã‰", "É"),
    ("ÃŠ", "Ê"),
    ("Ã‹", "Ë"),
    ("ÃŒ", "Ì"),
    ("Ã", "Í"),
    ("ÃŽ", "Î"),
    ("Ã", "Ï"),
    ("Ã", "Ð"),
    ("Ã‘", "Ñ"),
    ("Ã’", "Ò"),
    ("Ã“", "Ó"),
    ("Ã”", "Ô"),
    ("Ã•", "Õ"),
    ("Ã–", "Ö"),
    ("Ã—", "×"),
    ("Ã˜", "Ø"),
    ("Ã™", "Ù"),
    ("Ãš", "Ú"),
    ("Ã›", "Û"),
    ("Ãœ", "Ü"),
    ("Ã", "Ý"),
    ("Ãž", "Þ"),
    ("ÃŸ", "ß"),
]


def detect_and_decode(content: bytes) -> str:
    """Decode raw bytes into a string trying common encodings in order.

    Encodings tried:
    1. utf-8-sig (handles UTF-8 with BOM)
    2. utf-8
    3. cp1252 (standard Windows Western)
    4. iso-8859-1 (Latin-1)
    5. utf-16
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "iso-8859-1", "utf-16"):
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    # Fallback: decode with utf-8 replace to never raise
    return content.decode("utf-8", errors="replace")


def fix_pua_and_symbol_fonts(text: str) -> str:
    """Replace Private Use Area characters and font symbol artifacts with standard Unicode."""
    if not text:
        return text

    for pua_char, std_char in PUA_SYMBOL_MAP.items():
        if pua_char in text:
            text = text.replace(pua_char, std_char)

    return text


# Sort replacements by length of 'bad' pattern descending so longest prefixes match first
_SORTED_MOJIBAKE: list[tuple[str, str]] = sorted(
    MOJIBAKE_REPLACEMENTS, key=lambda pair: len(pair[0]), reverse=True
)


def fix_mojibake_patterns(text: str) -> str:
    """Fix common double-encoded UTF-8 and Latin-1/CP1252 mojibake sequences."""
    if not text:
        return text

    # Step 1: Explicit known mapping replacements (longest first)
    for bad, good in _SORTED_MOJIBAKE:
        if bad in text:
            text = text.replace(bad, good)

    # Step 2: Attempt algorithmic latin1 -> utf8 recovery for remaining multi-byte sequences
    # Only if text contains typical mojibake indicators like 'Ã', 'Â', or 'â'
    if any(m in text for m in ("Ã", "Â", "â")):
        try:
            # Try to fix by re-encoding to latin-1 and decoding as utf-8
            re_encoded = text.encode("latin-1")
            recovered = re_encoded.decode("utf-8")
            # If successful and reasonable length, use recovered text
            if len(recovered) > 0:
                text = recovered
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    return text


def normalize_unicode_text(text: str | None) -> str:
    """Complete Unicode normalization pipeline.

    Steps:
    1. Fix PUA symbol font characters (e.g. \\uF8E9 -> ©).
    2. Fix mojibake and double-encoded UTF-8 sequences.
    3. Apply canonical Unicode NFC normalization (unicodedata.normalize('NFC')).
    4. Strip NUL bytes (\\x00) for PostgreSQL compatibility.
    5. Clean trailing/leading non-printable control characters while preserving newlines and tabs.
    """
    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    # 1. Fix PUA characters
    text = fix_pua_and_symbol_fonts(text)

    # 2. Fix mojibake
    text = fix_mojibake_patterns(text)

    # 3. Canonical NFC composition
    text = unicodedata.normalize("NFC", text)

    # 4. Strip null bytes for PostgreSQL
    text = text.replace("\x00", "")

    # 5. Clean non-printable control characters except \n, \t, \r
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text
