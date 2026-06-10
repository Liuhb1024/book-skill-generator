from pathlib import Path

import pytest

from app.parsers.base import ParseError
from app.pipeline.stage0_extract import extract


def test_extract_txt_detects_chinese_chapters(tmp_path):
    txt_path = tmp_path / "book.txt"
    txt_path.write_text(
        """
前言内容

第一章 为什么学习

学习很重要。

第二章 如何学习

费曼技巧很好用。

第三章 学习的科学

脑科学研究表明。
""",
        encoding="utf-8",
    )

    meta, chapters, full_text = extract(txt_path)

    assert meta.format == "txt"
    assert meta.chapter_count >= 2
    assert meta.fallback_chunking is False
    assert len(chapters) >= 2
    assert chapters[0].title == "为什么学习"
    assert "费曼技巧" in full_text


def test_extract_plain_text_fallback_chunks(tmp_path):
    txt_path = tmp_path / "plain.txt"
    txt_path.write_text("这是一段没有任何章节标记的纯文本。" * 100, encoding="utf-8")

    meta, chapters, full_text = extract(txt_path)

    assert meta.fallback_chunking is True
    assert meta.chapter_count == len(chapters)
    assert len(chapters) > 0
    assert full_text


def test_extract_unsupported_format_raises_parse_error(tmp_path):
    doc_path = tmp_path / "book.doc"
    doc_path.write_text("not supported", encoding="utf-8")

    with pytest.raises(ParseError) as exc_info:
        extract(doc_path)

    assert exc_info.value.recoverable is False


def test_extract_missing_file_raises_parse_error():
    with pytest.raises(ParseError):
        extract(Path("test_fixtures/missing.txt"))
