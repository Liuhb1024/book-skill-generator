from pathlib import Path

from app.models import BookFormat, BookMeta
from app.parsers.base import BaseParser, ParseError


class TxtParser(BaseParser):
    def parse(self, filepath: Path) -> tuple[str, BookMeta]:
        if not filepath.exists():
            raise ParseError(f"文件不存在: {filepath}", filepath)
        if filepath.suffix.lower() not in (".txt", ".md"):
            raise ParseError(f"不支持的格式: {filepath.suffix}", filepath)

        try:
            text = filepath.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = filepath.read_text(encoding="gbk")
            except UnicodeDecodeError:
                text = filepath.read_text(encoding="latin-1")

        if not text.strip():
            raise ParseError("文件内容为空", filepath)

        meta = BookMeta(
            format=BookFormat.TXT,
            total_chars=len(text),
            chapter_count=0,
        )
        return text, meta

    @staticmethod
    def format_supported() -> BookFormat:
        return BookFormat.TXT
