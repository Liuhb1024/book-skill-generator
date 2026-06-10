from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BookFormat(str, Enum):
    PDF = "pdf"
    EPUB = "epub"
    TXT = "txt"


class DistillDepth(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ChapterInfo(BaseModel):
    index: int
    number: str
    title: str
    content: str
    char_count: int


class BookMeta(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    format: BookFormat
    total_chars: int
    chapter_count: int
    fallback_chunking: bool = False


class SkeletonOutput(BaseModel):
    thesis: str = ""
    frameworks: list[dict] = Field(default_factory=list)
    chapter_index: list[dict] = Field(default_factory=list)
    glossary: list[dict] = Field(default_factory=list)
    distillable_score: float = 1.0


class ChapterOutput(BaseModel):
    chapter_number: str
    chapter_title: str
    frameworks: list[str] = Field(default_factory=list)
    methodologies: list[str] = Field(default_factory=list)
    cases: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    actionable_steps: list[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    success: bool
    zip_path: Optional[str] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    elapsed_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)
