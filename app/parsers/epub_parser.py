from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub

from app.models import BookFormat, BookMeta
from app.parsers.base import BaseParser, ParseError


class EpubParser(BaseParser):
    def parse(self, filepath: Path) -> tuple[str, BookMeta]:
        if not filepath.exists():
            raise ParseError(f"文件不存在: {filepath}", filepath)
        if filepath.suffix.lower() != ".epub":
            raise ParseError(f"不支持的格式: {filepath.suffix}", filepath)

        try:
            book = epub.read_epub(str(filepath))
        except Exception as exc:
            raise ParseError(f"EPUB 文件无法打开，可能是 DRM 加密: {filepath}", filepath, recoverable=False) from exc

        parts = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text("\n", strip=True)
            if text:
                parts.append(text)

        text = "\n\n".join(parts).strip()
        if not text:
            raise ParseError("EPUB 未提取到文字", filepath)

        meta = BookMeta(
            title=self._first_metadata_value(book, "title"),
            author=self._first_metadata_value(book, "creator"),
            format=BookFormat.EPUB,
            total_chars=len(text),
            chapter_count=0,
        )
        return text, meta

    @staticmethod
    def format_supported() -> BookFormat:
        return BookFormat.EPUB

    @staticmethod
    def _first_metadata_value(book: epub.EpubBook, name: str) -> str | None:
        values = book.get_metadata("DC", name)
        if not values:
            return None
        value = values[0][0]
        return value.strip() if isinstance(value, str) and value.strip() else None
