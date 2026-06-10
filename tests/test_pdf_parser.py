from pathlib import Path

import fitz
import pytest

from app.models import BookFormat
from app.parsers.base import ParseError
from app.parsers.pdf_parser import PdfParser


def test_missing_file_raises_parse_error():
    parser = PdfParser()

    with pytest.raises(ParseError):
        parser.parse(Path("test_fixtures/missing.pdf"))


def test_non_pdf_raises_parse_error(sample_txt):
    parser = PdfParser()

    with pytest.raises(ParseError):
        parser.parse(sample_txt)


def test_valid_pdf_returns_text_and_meta():
    parser = PdfParser()

    text, meta = parser.parse(Path("test_fixtures/sample.pdf"))

    assert "Book Skill Generator PDF fixture" in text
    assert meta.format == BookFormat.PDF
    assert meta.total_chars > 0
    assert meta.chapter_count == 0


def test_short_pdf_raises_scan_detection_error(tmp_path):
    pdf_path = tmp_path / "short.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "short")
    doc.save(pdf_path)
    doc.close()

    parser = PdfParser()

    with pytest.raises(ParseError) as exc_info:
        parser.parse(pdf_path)

    assert "可能是扫描版" in exc_info.value.message
    assert exc_info.value.recoverable is False
