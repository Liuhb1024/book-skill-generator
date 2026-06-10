from pathlib import Path

from app.models import BookMeta, ChapterInfo
from app.parsers.base import BaseParser, ParseError
from app.parsers.chapter_detector import detect_chapters, fallback_chunk
from app.parsers.epub_parser import EpubParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.txt_parser import TxtParser


PARSERS: dict[str, type[BaseParser]] = {
    ".pdf": PdfParser,
    ".epub": EpubParser,
    ".txt": TxtParser,
    ".md": TxtParser,
}


def extract(filepath: Path) -> tuple[BookMeta, list[ChapterInfo], str]:
    parser_class = PARSERS.get(filepath.suffix.lower())
    if parser_class is None:
        raise ParseError(f"不支持的格式: {filepath.suffix}", filepath, recoverable=False)

    parser = parser_class()
    full_text, meta = parser.parse(filepath)

    chapters = detect_chapters(full_text)
    fallback_used = False
    if not chapters:
        chapters = fallback_chunk(full_text)
        fallback_used = True

    meta.chapter_count = len(chapters)
    meta.fallback_chunking = fallback_used
    return meta, chapters, full_text
