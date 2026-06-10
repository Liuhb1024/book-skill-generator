from pathlib import Path

import pytest

from app.models import BookFormat
from app.parsers.base import ParseError
from app.parsers.epub_parser import EpubParser


def test_missing_file_raises_parse_error():
    parser = EpubParser()

    with pytest.raises(ParseError):
        parser.parse(Path("test_fixtures/missing.epub"))


def test_non_epub_raises_parse_error(sample_txt):
    parser = EpubParser()

    with pytest.raises(ParseError):
        parser.parse(sample_txt)


def test_valid_epub_returns_text_and_meta():
    parser = EpubParser()

    text, meta = parser.parse(Path("test_fixtures/sample.epub"))

    assert "前言这是一本测试用书" in text
    assert "学习很重要" in text
    assert meta.format == BookFormat.EPUB
    assert meta.total_chars > 0
    assert meta.title
