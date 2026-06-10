import re

from app.models import ChapterInfo


SPECIAL_PATTERNS = [
    (re.compile(r"^\s*(引言|introduction)\s*[:：]?\s*(.*)$", re.IGNORECASE | re.MULTILINE), "intro", "引言"),
    (re.compile(r"^\s*(前言|preface)\s*[:：]?\s*(.*)$", re.IGNORECASE | re.MULTILINE), "preface", "前言"),
    (re.compile(r"^\s*(附录|appendix)\s*([A-Za-z一二三四五六七八九十0-9]*)\s*[:：]?\s*(.*)$", re.IGNORECASE | re.MULTILINE), "appendix", "附录"),
    (re.compile(r"^\s*(后记|epilogue)\s*[:：]?\s*(.*)$", re.IGNORECASE | re.MULTILINE), "epilogue", "后记"),
    (re.compile(r"^\s*(版权页|版权信息|目录|致谢|acknowledg(e)?ments?|contents)\s*[:：]?\s*(.*)$", re.IGNORECASE | re.MULTILINE), "fm", "前页"),
    (re.compile(r"^\s*(索引|参考文献|references|bibliography|index)\s*[:：]?\s*(.*)$", re.IGNORECASE | re.MULTILINE), "bm", "后页"),
]

CHAPTER_PATTERNS = [
    re.compile(r"^\s*第([零一二三四五六七八九十百千0-9]+)章[ \t]*[：:]*[ \t]*(.+)$", re.MULTILINE),
    re.compile(r"^\s*Chapter\s+(\d+|[IVX]+)[.:]?[ \t]*(.+)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(\d+)\.\s+(.+)$", re.MULTILINE),
    re.compile(r"^\s*PART\s+(\d+|[IVX]+)[.:]?[ \t]*(.+)$", re.IGNORECASE | re.MULTILINE),
]

CHINESE_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def detect_chapters(text: str) -> list[ChapterInfo]:
    markers = _detect_special_markers(text) + _detect_chapter_markers(text)
    if len([marker for marker in markers if marker["label"].startswith("ch")]) < 2:
        return []

    markers.sort(key=lambda item: item["start"])
    result = []
    for i, marker in enumerate(markers):
        next_start = markers[i + 1]["start"] if i + 1 < len(markers) else len(text)
        content = text[marker["start"]:next_start].strip()
        result.append(
            ChapterInfo(
                index=len(result),
                number=marker["display_number"],
                display_number=marker["display_number"],
                file_number=marker["file_number"],
                label=marker["label"],
                title=marker["title"],
                content=content,
                char_count=len(content),
            )
        )
    return result


def fallback_chunk(text: str, chunk_size: int = 5000) -> list[ChapterInfo]:
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk_text = text[i : i + chunk_size]
        chunk_number = len(chunks) + 1
        chunks.append(
            ChapterInfo(
                index=len(chunks),
                number=f"chunk-{chunk_number:02d}",
                display_number=f"chunk-{chunk_number:02d}",
                file_number=f"{chunk_number:02d}",
                label=f"ch{chunk_number:02d}",
                title=f"第{chunk_number}部分",
                content=chunk_text,
                char_count=len(chunk_text),
            )
        )
    return chunks


def distillable_chapters(chapters: list[ChapterInfo]) -> list[ChapterInfo]:
    return [chapter for chapter in chapters if chapter.label.startswith("ch")]


def _detect_chapter_markers(text: str) -> list[dict]:
    markers = []
    for pattern in CHAPTER_PATTERNS:
        matches = list(pattern.finditer(text))
        if len(matches) >= 2:
            for i, match in enumerate(matches):
                raw_number = match.group(1).strip()
                title = match.group(2).strip()
                file_number = _file_number(raw_number, i + 1)
                markers.append(
                    {
                        "start": match.start(),
                        "display_number": raw_number,
                        "file_number": file_number,
                        "label": f"ch{file_number}",
                        "title": title,
                    }
                )
            break
    return markers


def _detect_special_markers(text: str) -> list[dict]:
    markers = []
    for pattern, base_label, fallback_title in SPECIAL_PATTERNS:
        for match in pattern.finditer(text):
            title_parts = [part.strip() for part in match.groups() if isinstance(part, str) and part.strip()]
            display = title_parts[0] if title_parts else fallback_title
            suffix = ""
            if base_label == "appendix":
                appendix_id = title_parts[1] if len(title_parts) > 1 else ""
                suffix = f"-{appendix_id.lower()}" if appendix_id else ""
            label = f"{base_label}{suffix}"
            markers.append(
                {
                    "start": match.start(),
                    "display_number": display,
                    "file_number": label,
                    "label": label,
                    "title": " ".join(title_parts) or fallback_title,
                }
            )
    return markers


def _file_number(raw_number: str, fallback: int) -> str:
    if raw_number.isdigit():
        return f"{int(raw_number):02d}"
    value = _chinese_to_int(raw_number)
    if value is None:
        value = _roman_to_int(raw_number)
    if value is None:
        value = fallback
    return f"{value:02d}"


def _chinese_to_int(raw: str) -> int | None:
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    if raw in CHINESE_NUMBERS:
        return CHINESE_NUMBERS[raw]
    if "十" in raw:
        parts = raw.split("十")
        tens = CHINESE_NUMBERS.get(parts[0], 1) if parts[0] else 1
        ones = CHINESE_NUMBERS.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    return None


def _roman_to_int(raw: str) -> int | None:
    values = {"I": 1, "V": 5, "X": 10}
    total = 0
    previous = 0
    for char in reversed(raw.upper()):
        value = values.get(char)
        if value is None:
            return None
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    return total or None
