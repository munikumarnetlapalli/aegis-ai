"""Unit tests for Unicode normalization, mojibake repair, and encoding safety."""
import pytest
from app.ingestion.normalizer import (
    detect_and_decode,
    fix_mojibake_patterns,
    fix_pua_and_symbol_fonts,
    normalize_unicode_text,
)
from app.ingestion.parser import DocumentParser


class TestUnicodePreservation:
    """Verify that essential legal and typographical Unicode characters are preserved intact."""

    @pytest.mark.parametrize(
        "char,name",
        [
            ("©", "copyright"),
            ("’", "right single quote"),
            ("‘", "left single quote"),
            ("“", "left double quote"),
            ("”", "right double quote"),
            ("–", "en-dash"),
            ("—", "em-dash"),
            ("§", "section sign"),
            ("•", "bullet point"),
            ("€", "euro sign"),
            ("£", "pound sign"),
            ("¥", "yen sign"),
            ("é", "e acute"),
            ("ü", "u umlaut"),
            ("ñ", "n tilde"),
            ("ç", "c cedilla"),
        ],
    )
    def test_preserves_target_unicode_characters(self, char: str, name: str):
        text = f"Sample text with {char} ({name}) in legal insurance policy § 4.2."
        result = normalize_unicode_text(text)
        assert char in result
        assert result == text

    def test_preserves_combined_provenance_symbols(self):
        text = "Source: publication-aut-pp-consumer-auto.pdf §— p.7"
        result = normalize_unicode_text(text)
        assert result == text
        assert "§—" in result


class TestPUAAndFontSymbolFixes:
    """Verify mapping of PDF Private Use Area (PUA) symbol font characters."""

    def test_pua_copyright_fixed(self):
        text = "\uf8e92022 NATIONAL ASSOCIATION OF INSURANCE COMMISSIONERS"
        result = normalize_unicode_text(text)
        assert result.startswith("©2022")
        assert "\uf8e9" not in result

    def test_pua_bullet_and_section_fixed(self):
        text = "\uf0a7 4.1 \uf0b7 Item description"
        result = normalize_unicode_text(text)
        assert result == "§ 4.1 • Item description"


class TestMojibakeFixes:
    """Verify repair of Latin-1 / CP1252 and MacRoman mojibake corruptions."""

    def test_fixes_pdf_macroman_copyright_artifact(self):
        # 'ï£©2022' was observed in PDF extraction
        text = "ï£©2022 NATIONAL ASSOCIATION OF INSURANCE COMMISSIONERS"
        result = normalize_unicode_text(text)
        assert result.startswith("©2022")

    def test_fixes_double_encoded_apostrophe(self):
        text = "A CONSUMERâ€™S GUIDE TO AUTO INSURANCE"
        result = normalize_unicode_text(text)
        assert "A CONSUMER’S GUIDE" in result

    def test_fixes_double_encoded_section_and_dashes(self):
        text = "Â§ 12.3 â€” Standard Policy Terms"
        result = normalize_unicode_text(text)
        assert "§ 12.3 — Standard Policy Terms" in result

    def test_fixes_latin1_accented_characters(self):
        text = "RÃ©sumÃ© of insurance coverage"
        result = normalize_unicode_text(text)
        assert result == "Résumé of insurance coverage"


class TestMultiEncodingDetection:
    """Verify robust decoding across UTF-8, UTF-8-SIG, CP1252, and Latin-1."""

    def test_decode_utf8_with_bom(self):
        raw = b"\xef\xbb\xbf\xc2\xa9 2026 AegisAI Policy"
        text = detect_and_decode(raw)
        assert text == "© 2026 AegisAI Policy"

    def test_decode_cp1252_smart_quotes_and_dashes(self):
        # In CP1252: \x92 is ’, \x97 is —, \xa9 is ©, \xa7 is §
        raw = b"Insurer\x92s policy \xa7 10 \x97 \xa9 2026"
        text = detect_and_decode(raw)
        normalized = normalize_unicode_text(text)
        assert "Insurer’s policy § 10 — © 2026" in normalized

    def test_decode_latin1_accents(self):
        raw = "Éligibilité de l'assuré".encode("iso-8859-1")
        text = detect_and_decode(raw)
        assert "Éligibilité" in text


class TestParserUnicodeIntegration:
    """Verify DocumentParser handles Unicode seamlessly across file types."""

    def test_parse_txt_with_unicode_and_symbols(self):
        content = (
            "POLICY SCHEDULE § 1.0\n\n"
            "© 2026 All rights reserved.\n\n"
            "Coverage extends to driver’s vehicle — comprehensive & collision."
        ).encode("utf-8")

        parser = DocumentParser()
        result = parser.parse(content, filename="policy_test.txt", content_type="text/plain")

        assert result.page_count > 0
        full = result.full_text
        assert "§ 1.0" in full
        assert "© 2026" in full
        assert "driver’s" in full
        assert "—" in full

    def test_strip_null_bytes(self):
        dirty = "Clean text with\x00 null\x00 bytes."
        cleaned = normalize_unicode_text(dirty)
        assert "\x00" not in cleaned
        assert cleaned == "Clean text with null bytes."
