from app.parsers.chapter_detector import detect_chapters, fallback_chunk


def test_detect_chinese_chapters():
    text = """
前言内容随便写写

第一章 为什么学习

这是第一章的内容。学习很重要。

第二章 如何学习

这是第二章的内容。费曼技巧很好用。

第三章 学习的科学

这是第三章的内容。脑科学研究表明。
"""
    chapters = detect_chapters(text)
    assert len(chapters) >= 3
    assert chapters[0].title == "为什么学习"
    assert chapters[1].title == "如何学习"


def test_detect_english_chapters():
    text = """
Preface stuff

Chapter 1: Why We Learn

Learning is fundamental.

Chapter 2: How to Learn

The Feynman technique is great.

Chapter 3: The Science of Learning

Brain research shows.
"""
    chapters = detect_chapters(text)
    assert len(chapters) >= 3
    assert "1" in chapters[0].number
    assert "2" in chapters[1].number


def test_no_chapters_returns_empty():
    text = "这是一段没有任何章节标记的纯文本。" * 100
    chapters = detect_chapters(text)
    assert chapters == []


def test_fallback_chunk():
    text = "ABC" * 3000
    chunks = fallback_chunk(text, chunk_size=3000)
    assert len(chunks) == 3
    assert chunks[0].char_count == 3000
    assert chunks[-1].char_count == 3000


def test_fallback_chunk_labels():
    text = "X" * 6000
    chunks = fallback_chunk(text, chunk_size=3000)
    assert chunks[0].number == "chunk-01"
    assert chunks[1].number == "chunk-02"
