from abc import ABC, abstractmethod
from pathlib import Path

from app.models import BookFormat, BookMeta


class BaseParser(ABC):
    @abstractmethod
    def parse(self, filepath: Path) -> tuple[str, BookMeta]:
        ...

    @staticmethod
    def format_supported() -> BookFormat:
        raise NotImplementedError


class ParseError(Exception):
    def __init__(self, message: str, filepath: Path, recoverable: bool = True):
        self.message = message
        self.filepath = filepath
        self.recoverable = recoverable
        super().__init__(message)
