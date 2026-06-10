import re

from app.models import ChapterInfo


CHAPTER_PATTERNS = [
    re.compile(r"^\s*第([零一二三四五六七八九十百千0-9]+)章[ \t]*[：:]*[ \t]*(.+)$", re.MULTILINE),
    re.compile(r"^\s*Chapter\s+(\d+|[IVX]+)[.:]?[ \t]*(.+)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(\d+)\.\s+(.+)$", re.MULTILINE),
    re.compile(r"^\s*PART\s+(\d+|[IVX]+)[.:]?[ \t]*(.+)$", re.IGNORECASE | re.MULTILINE),
]


def detect_chapters(text: str) -> list[ChapterInfo]:
    chapters = []
    for pattern in CHAPTER_PATTERNS:
        matches = list(pattern.finditer(text))
        if len(matches) >= 3:
            for i, m in enumerate(matches):
                number = m.group(1).strip() if m.lastindex and m.lastindex >= 1 else str(i + 1)
                title = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else m.group(0).strip()
                start = m.start()
                chapters.append((start, number, title))
            break

    if not chapters:
        return []

    chapters.sort(key=lambda x: x[0])
    result = []
    for i, (start, number, title) in enumerate(chapters):
        next_start = chapters[i + 1][0] if i + 1 < len(chapters) else len(text)
        content = text[start:next_start].strip()
        result.append(
            ChapterInfo(
                index=i,
                number=number,
                title=title,
                content=content,
                char_count=len(content),
            )
        )
    return result


def fallback_chunk(text: str, chunk_size: int = 5000) -> list[ChapterInfo]:
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk_text = text[i : i + chunk_size]
        chunks.append(
            ChapterInfo(
                index=len(chunks),
                number=f"chunk-{len(chunks) + 1:02d}",
                title=f"第{len(chunks) + 1}部分",
                content=chunk_text,
                char_count=len(chunk_text),
            )
        )
    return chunks
