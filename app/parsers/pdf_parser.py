from pathlib import Path

import fitz

from app.models import BookFormat, BookMeta
from app.parsers.base import BaseParser, ParseError


class PdfParser(BaseParser):
    def parse(self, filepath: Path) -> tuple[str, BookMeta]:
        if not filepath.exists():
            raise ParseError(f"文件不存在: {filepath}", filepath)
        if filepath.suffix.lower() != ".pdf":
            raise ParseError(f"不支持的格式: {filepath.suffix}", filepath)

        try:
            with fitz.open(filepath) as doc:
                text = "\n".join(page.get_text("text") for page in doc)
        except Exception as exc:
            raise ParseError(f"PDF 文件无法打开: {filepath}", filepath) from exc

        text = text.strip()
        if len(text) < 50:
            raise ParseError("PDF 提取文字过少，可能是扫描版", filepath, recoverable=False)

        meta = BookMeta(
            format=BookFormat.PDF,
            total_chars=len(text),
            chapter_count=0,
        )
        return text, meta

    @staticmethod
    def format_supported() -> BookFormat:
        return BookFormat.PDF
