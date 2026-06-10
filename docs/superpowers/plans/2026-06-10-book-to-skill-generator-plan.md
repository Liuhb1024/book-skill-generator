# Book Skill Generator 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Web 工具，用户上传 PDF/EPUB/TXT，系统自动调用 DeepSeek API 蒸馏成 Claude Code Skill 文件包。

**Architecture:** 五阶段 Map-Reduce 管线（文本提取 → 骨架提取 → 并行章节蒸馏 → 知识整合 → 打包输出），FastAPI 后端 + Vue 3 CDN 前端，SSE 实时进度推送。

**Tech Stack:** Python 3.11+ / FastAPI / PyMuPDF / ebooklib / OpenAI SDK (DeepSeek 兼容) / Jinja2 / Vue 3 CDN / Docker

---

## 文件结构设计

```
book-skill-generator/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口 + 路由
│   ├── config.py                  # 配置（API key、模型、路径）
│   ├── models.py                  # Pydantic 数据模型
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── runner.py              # 管线编排器
│   │   ├── stage0_extract.py      # 文本提取
│   │   ├── stage1_skeleton.py     # 骨架提取
│   │   ├── stage2_chapters.py     # 并行章节蒸馏
│   │   ├── stage3_integrate.py    # 知识整合
│   │   └── stage4_package.py      # 打包输出
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py                # 解析器基类 + 统一接口
│   │   ├── pdf_parser.py          # PDF → 纯文本
│   │   ├── epub_parser.py         # EPUB → 纯文本
│   │   ├── txt_parser.py          # TXT → 纯文本
│   │   └── chapter_detector.py    # 章节识别
│   ├── prompts/
│   │   ├── skeleton.py            # 阶段 1 prompt 模板
│   │   ├── chapter.py             # 阶段 2 prompt 模板
│   │   └── integrate.py           # 阶段 3 prompt 模板
│   ├── templates/
│   │   ├── SKILL.md.j2            # SKILL.md Jinja2 模板
│   │   └── README.md.j2           # 使用说明 Jinja2 模板
│   └── static/
│       ├── index.html             # 前端页面
│       └── style.css
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # pytest fixtures
│   ├── test_pdf_parser.py
│   ├── test_epub_parser.py
│   ├── test_chapter_detector.py
│   ├── test_stage0_extract.py
│   ├── test_stage1_skeleton.py
│   ├── test_stage2_chapters.py
│   ├── test_stage3_integrate.py
│   ├── test_stage4_package.py
│   ├── test_runner.py
│   └── test_main.py
├── test_fixtures/                 # 测试用的小样本文件
│   ├── sample.pdf
│   ├── sample.epub
│   └── sample.txt
├── requirements.txt
├── Dockerfile
├── .gitignore
└── .env.example
```

**设计原则：**
- 每个 parser 一个文件，共享基类 `base.py`（单一职责）
- prompt 模板用 Python 字符串常量而非 .txt 文件（减少 IO，避免编码问题）
- pipeline 各阶段独立模块，通过 `runner.py` 编排（每个阶段可独立测试）
- Pydantic 模型统一定义在 `models.py`（跨模块共享的数据结构）

---

## Phase 1: 核心管线（MVP）

### Task 1: 项目脚手架 + 依赖

**Files:**
- Create: `requirements.txt`, `.env.example`, `app/__init__.py`, `app/config.py`, `app/models.py`, `tests/__init__.py`, `tests/conftest.py`, `test_fixtures/sample.txt`

- [ ] **Step 1: 创建 requirements.txt**

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.19
openai==1.68.0
PyMuPDF==1.25.2
ebooklib==0.18
beautifulsoup4==4.12.3
Jinja2==3.1.4
pydantic==2.10.4
python-dotenv==1.0.1
aiofiles==24.1.0
sse-starlette==2.2.1
```

- [ ] **Step 2: 创建 .env.example**

```env
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_LITE_MODEL=deepseek-chat
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
```

- [ ] **Step 3: 创建 app/__init__.py**

```python
"""Book Skill Generator - Distill books into Claude Code skills."""
```

- [ ] **Step 4: 创建 app/config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_LITE_MODEL: str = os.getenv("DEEPSEEK_LITE_MODEL", "deepseek-chat")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./outputs")
    MAX_FILE_SIZE_MB: int = 50
    MAX_CONCURRENT_CHAPTERS: int = 10
    CHAPTER_RETRY_COUNT: int = 2


settings = Settings()
```

- [ ] **Step 5: 创建 app/models.py**

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


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


class PipelineProgress(BaseModel):
    stage: str
    message: str
    percent: float
    detail: Optional[str] = None


class PipelineResult(BaseModel):
    success: bool
    zip_path: Optional[str] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    elapsed_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)
```

- [ ] **Step 6: 创建 tests/conftest.py**

```python
import pytest
from pathlib import Path


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent.parent / "test_fixtures"


@pytest.fixture
def sample_txt(fixtures_dir):
    return fixtures_dir / "sample.txt"


@pytest.fixture
def sample_txt_content():
    return """前言

这是一本关于学习方法的书。

第一章 为什么学习

第一节 学习的本质

学习是人类最基础的能力之一。通过刻意练习，任何人都能掌握新技能。
研究表明，间隔重复比集中练习更有效。

第二节 元认知

元认知是指对自己思维过程的理解和控制。善于学习的人往往具有高度的元认知能力。

第二章 如何学习

第一节 费曼技巧

理查德·费曼提出了一种高效的学习方法：用自己的话解释一个概念，
如果说不清楚，说明还没真正理解。

第二节 番茄工作法

将工作时间分割成25分钟的段落，中间休息5分钟。
这种方法可以有效防止疲劳，提高专注度。

后记

学习是一场终身的旅程。
"""
```

- [ ] **Step 7: 创建测试用 sample.txt**

```bash
mkdir -p test_fixtures
# 将 conftest 中的 sample_txt_content 写入 test_fixtures/sample.txt
```

- [ ] **Step 8: 安装依赖**

```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

- [ ] **Step 9: 验证脚手架**

```bash
python -c "from app.config import settings; print('Config OK')"
python -c "from app.models import PipelineResult; print('Models OK')"
```

- [ ] **Step 10: Commit**

```bash
git add requirements.txt .env.example app/__init__.py app/config.py app/models.py tests/ tests/conftest.py test_fixtures/sample.txt
git commit -m "feat: project scaffold with config, models, and test fixtures"
```

---

### Task 2: TXT 解析器 + 章节检测器

**Files:**
- Create: `app/parsers/__init__.py`, `app/parsers/base.py`, `app/parsers/txt_parser.py`, `app/parsers/chapter_detector.py`
- Create: `tests/test_chapter_detector.py`

- [ ] **Step 1: 创建解析器基类 app/parsers/base.py**

```python
from abc import ABC, abstractmethod
from pathlib import Path
from app.models import BookMeta, ChapterInfo, BookFormat


class BaseParser(ABC):
    @abstractmethod
    def parse(self, filepath: Path) -> tuple[str, BookMeta]:
        """Parse file, return (full_text, metadata)."""
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
```

- [ ] **Step 2: 创建章节检测器 app/parsers/chapter_detector.py**

```python
import re
from app.models import ChapterInfo


CHAPTER_PATTERNS = [
    re.compile(r"第[零一二三四五六七八九十百千0-9]+章\s*[：:]*\s*(.+)"),
    re.compile(r"Chapter\s+(\d+|[IVX]+)[.:]?\s*(.+)", re.IGNORECASE),
    re.compile(r"^(\d+)\.\s+(.+)$", re.MULTILINE),
    re.compile(r"PART\s+(\d+|[IVX]+)[.:]?\s*(.+)", re.IGNORECASE),
]


def detect_chapters(text: str) -> list[ChapterInfo]:
    """从文本中检测章节目录。返回按出现顺序的章节列表。"""
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
        result.append(ChapterInfo(
            index=i,
            number=number,
            title=title,
            content=content,
            char_count=len(content),
        ))
    return result


def fallback_chunk(text: str, chunk_size: int = 5000) -> list[ChapterInfo]:
    """章节检测失败时的均匀分块降级方案。"""
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk_text = text[i:i + chunk_size]
        chunks.append(ChapterInfo(
            index=len(chunks),
            number=f"chunk-{len(chunks) + 1:02d}",
            title=f"第{len(chunks) + 1}部分",
            content=chunk_text,
            char_count=len(chunk_text),
        ))
    return chunks
```

- [ ] **Step 3: 创建 TXT 解析器 app/parsers/txt_parser.py**

```python
from pathlib import Path
from app.parsers.base import BaseParser, ParseError
from app.models import BookMeta, BookFormat


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
```

- [ ] **Step 4: 创建 app/parsers/__init__.py**

```python
from app.parsers.txt_parser import TxtParser
from app.parsers.base import ParseError

__all__ = ["TxtParser", "ParseError"]
```

- [ ] **Step 5: 编写章节检测测试 tests/test_chapter_detector.py**

```python
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
    assert chapters[2].number == "三"


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
```

- [ ] **Step 6: 运行测试验证失败（TXT parser 未引入）**

```bash
python -m pytest tests/test_chapter_detector.py -v
```

Expected: 4 pass

- [ ] **Step 7: Commit**

```bash
git add app/parsers/ tests/test_chapter_detector.py
git commit -m "feat: add TXT parser, chapter detector, and parser base class"
```

---

### Task 3: PDF 解析器

**Files:**
- Create: `app/parsers/pdf_parser.py`
- Create: `tests/test_pdf_parser.py`

- [ ] **Step 1: 创建 PDF 解析器 app/parsers/pdf_parser.py**

```python
from pathlib import Path
from app.parsers.base import BaseParser, ParseError
from app.models import BookMeta, BookFormat


class PdfParser(BaseParser):
    def parse(self, filepath: Path) -> tuple[str, BookMeta]:
        if not filepath.exists():
            raise ParseError(f"文件不存在: {filepath}", filepath)
        if filepath.suffix.lower() != ".pdf":
            raise ParseError(f"不是 PDF 文件: {filepath.suffix}", filepath)

        try:
            import fitz
            doc = fitz.open(str(filepath))
        except ImportError:
            raise ParseError("PyMuPDF (fitz) 未安装", filepath)
        except Exception as e:
            raise ParseError(f"无法打开 PDF: {e}", filepath)

        if doc.page_count == 0:
            doc.close()
            raise ParseError("PDF 为空", filepath)

        pages_text = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages_text.append(text)

        doc.close()

        full_text = "\n\n".join(pages_text)

        if len(full_text.strip()) < 50:
            raise ParseError(
                "PDF 文字量极少，可能是扫描版（无文字层）。请使用 EPUB 格式或 OCR 处理后的 PDF。",
                filepath,
                recoverable=False,
            )

        meta = BookMeta(
            format=BookFormat.PDF,
            total_chars=len(full_text),
            chapter_count=0,
        )
        return full_text, meta

    @staticmethod
    def format_supported() -> BookFormat:
        return BookFormat.PDF
```

- [ ] **Step 2: 创建 PDF 解析器测试 tests/test_pdf_parser.py**

```python
import pytest
from pathlib import Path
from app.parsers.pdf_parser import PdfParser
from app.parsers.base import ParseError


def test_pdf_parser_file_not_found():
    parser = PdfParser()
    with pytest.raises(ParseError, match="文件不存在"):
        parser.parse(Path("/nonexistent/file.pdf"))


def test_pdf_parser_wrong_format():
    parser = PdfParser()
    with pytest.raises(ParseError, match="不是 PDF"):
        parser.parse(Path("test.txt"))


def test_pdf_parser_valid_pdf(fixtures_dir):
    parser = PdfParser()
    pdf_path = fixtures_dir / "sample.pdf"
    if not pdf_path.exists():
        pytest.skip("sample.pdf not available")
    text, meta = parser.parse(pdf_path)
    assert len(text) > 0
    assert meta.format.value == "pdf"
    assert meta.total_chars > 0
```

- [ ] **Step 3: 生成一个最小测试 PDF fixtures/sample.pdf（Python 脚本）**

```bash
python3 -c "
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), '前言\n\n这是一本测试书。\n\n第一章 测试章节\n\n这是第一章的内容，包含足够的文字来通过最小文字量检测。' * 10)
doc.save('test_fixtures/sample.pdf')
doc.close()
print('sample.pdf created')
"
```

- [ ] **Step 4: 运行测试**

```bash
python -m pytest tests/test_pdf_parser.py -v
```

Expected: PASS (or skip if fitz not installed)

- [ ] **Step 5: Commit**

```bash
git add app/parsers/pdf_parser.py tests/test_pdf_parser.py
git commit -m "feat: add PDF parser with scan detection and minimal-text guard"
```

---

### Task 4: EPUB 解析器

**Files:**
- Create: `app/parsers/epub_parser.py`
- Create: `tests/test_epub_parser.py`

- [ ] **Step 1: 创建 EPUB 解析器 app/parsers/epub_parser.py**

```python
from pathlib import Path
from app.parsers.base import BaseParser, ParseError
from app.models import BookMeta, BookFormat


class EpubParser(BaseParser):
    def parse(self, filepath: Path) -> tuple[str, BookMeta]:
        if not filepath.exists():
            raise ParseError(f"文件不存在: {filepath}", filepath)
        if filepath.suffix.lower() != ".epub":
            raise ParseError(f"不是 EPUB 文件: {filepath.suffix}", filepath)

        try:
            from ebooklib import epub
            from bs4 import BeautifulSoup
        except ImportError as e:
            raise ParseError(f"依赖未安装: {e}", filepath)

        try:
            book = epub.read_epub(str(filepath))
        except Exception as e:
            raise ParseError(f"无法打开 EPUB（可能是 DRM 加密）: {e}", filepath, recoverable=False)

        texts = []
        for item in book.get_items_of_type(9):
            soup = BeautifulSoup(item.get_body_content(), "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            if text:
                texts.append(text)

        if not texts:
            raise ParseError("EPUB 中未提取到文字内容", filepath)

        full_text = "\n\n".join(texts)

        title = ""
        author = ""
        if book.get_metadata("DC", "title"):
            title = str(book.get_metadata("DC", "title")[0][0])
        if book.get_metadata("DC", "creator"):
            author = str(book.get_metadata("DC", "creator")[0][0])

        meta = BookMeta(
            title=title or None,
            author=author or None,
            format=BookFormat.EPUB,
            total_chars=len(full_text),
            chapter_count=0,
        )
        return full_text, meta

    @staticmethod
    def format_supported() -> BookFormat:
        return BookFormat.EPUB
```

- [ ] **Step 2: 创建 EPUB 解析器测试 tests/test_epub_parser.py**

```python
import pytest
from pathlib import Path
from app.parsers.epub_parser import EpubParser
from app.parsers.base import ParseError


def test_epub_parser_file_not_found():
    parser = EpubParser()
    with pytest.raises(ParseError, match="文件不存在"):
        parser.parse(Path("/nonexistent/file.epub"))


def test_epub_parser_wrong_format():
    parser = EpubParser()
    with pytest.raises(ParseError, match="不是 EPUB"):
        parser.parse(Path("test.txt"))


def test_epub_parser_valid_epub(fixtures_dir):
    parser = EpubParser()
    epub_path = fixtures_dir / "sample.epub"
    if not epub_path.exists():
        pytest.skip("sample.epub not available")
    text, meta = parser.parse(epub_path)
    assert len(text) > 0
    assert meta.format.value == "epub"
    assert meta.total_chars > 0
```

- [ ] **Step 3: 生成一个最小测试 EPUB（Python 脚本）**

```bash
python3 -c "
from ebooklib import epub
book = epub.EpubBook()
book.set_identifier('test123')
book.set_title('测试书')
book.set_language('zh')
c1 = epub.EpubHtml(title='前言', file_name='preface.xhtml')
c1.content = '<h1>前言</h1><p>这是一本测试用书。</p>'
c2 = epub.EpubHtml(title='第一章 测试', file_name='ch01.xhtml')
c2.content = '<h1>第一章 测试</h1><p>这是第一章的内容。' + '学习很重要。' * 100 + '</p>'
book.add_item(c1)
book.add_item(c2)
book.spine = ['nav', c1, c2]
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())
epub.write_epub('test_fixtures/sample.epub', book)
print('sample.epub created')
"
```

- [ ] **Step 4: 运行测试**

```bash
python -m pytest tests/test_epub_parser.py -v
```

Expected: PASS (or skip if ebooklib not installed)

- [ ] **Step 5: Commit**

```bash
git add app/parsers/epub_parser.py tests/test_epub_parser.py test_fixtures/sample.epub
git commit -m "feat: add EPUB parser with DRM detection and metadata extraction"
```

---

### Task 5: Stage 0 整合 — 文本提取入口

**Files:**
- Create: `app/pipeline/__init__.py`, `app/pipeline/stage0_extract.py`
- Create: `tests/test_stage0_extract.py`

- [ ] **Step 1: 创建 app/pipeline/stage0_extract.py**

```python
from pathlib import Path
from app.parsers.pdf_parser import PdfParser
from app.parsers.epub_parser import EpubParser
from app.parsers.txt_parser import TxtParser
from app.parsers.chapter_detector import detect_chapters, fallback_chunk
from app.parsers.base import ParseError
from app.models import BookMeta, ChapterInfo


PARSERS = {
    "pdf": PdfParser(),
    "epub": EpubParser(),
    "txt": TxtParser(),
}


def extract(filepath: Path) -> tuple[BookMeta, list[ChapterInfo], str]:
    """解析文件，返回 (元数据, 章节列表, 原始全文)。"""
    suffix = filepath.suffix.lower().lstrip(".")
    parser = PARSERS.get(suffix)
    if parser is None:
        raise ParseError(f"不支持的格式: {suffix}，支持 PDF/EPUB/TXT", filepath, recoverable=False)

    full_text, meta = parser.parse(filepath)

    chapters = detect_chapters(full_text)
    fallback_used = False
    if not chapters:
        chapters = fallback_chunk(full_text)
        fallback_used = True

    meta.chapter_count = len(chapters)
    meta.fallback_chunking = fallback_used

    return meta, chapters, full_text
```

- [ ] **Step 2: 创建测试 tests/test_stage0_extract.py**

```python
from pathlib import Path
from app.pipeline.stage0_extract import extract
from app.parsers.base import ParseError
import pytest


def test_extract_txt_with_chapters(sample_txt):
    meta, chapters, full_text = extract(Path(str(sample_txt)))
    assert meta.format.value == "txt"
    assert meta.total_chars > 0
    assert len(chapters) >= 2
    assert chapters[0].content
    assert chapters[0].char_count > 0


def test_extract_txt_no_chapters_falls_back():
    text = "没有任何章节标记的内容。" * 200
    tmp = Path("/tmp/test_no_chapters.txt")
    tmp.write_text(text)
    try:
        meta, chapters, _ = extract(tmp)
        assert meta.fallback_chunking is True
        assert len(chapters) > 0
    finally:
        tmp.unlink(missing_ok=True)


def test_extract_unsupported_format():
    with pytest.raises(ParseError, match="不支持的格式"):
        extract(Path("/tmp/test.doc"))


def test_extract_file_not_found():
    with pytest.raises(ParseError):
        extract(Path("/tmp/does_not_exist.epub"))
```

- [ ] **Step 3: 运行测试**

```bash
python -m pytest tests/test_stage0_extract.py -v
```

Expected: 4 pass (其中 PDF/EPUB 相关可能 skip)

- [ ] **Step 4: Commit**

```bash
git add app/pipeline/__init__.py app/pipeline/stage0_extract.py tests/test_stage0_extract.py
git commit -m "feat: add stage0 extract entry point with parser dispatch and fallback chunking"
```

---

### Task 6: Prompt 模板 + AI 客户端

**Files:**
- Create: `app/prompts/skeleton.py`, `app/prompts/chapter.py`, `app/prompts/integrate.py`
- Create: `app/ai_client.py`

- [ ] **Step 1: 创建 app/ai_client.py**

```python
import json
from openai import OpenAI
from app.config import settings


_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    return _client


def call_ai(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    response_format: str = "json_object",
    max_tokens: int = 4096,
) -> tuple[str, int, int]:
    """调用 AI，返回 (响应文本, prompt_tokens, completion_tokens)。"""
    client = get_client()
    model = model or settings.DEEPSEEK_MODEL

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": response_format} if response_format else None,
    )

    content = response.choices[0].message.content or ""
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0

    return content, prompt_tokens, completion_tokens


def estimate_cost(prompt_tokens: int, completion_tokens: int, model: str | None = None) -> float:
    """估算成本（人民币），按 DeepSeek 定价。"""
    price_per_m_input = 1.0 / 1_000_000
    price_per_m_output = 4.0 / 1_000_000
    return (prompt_tokens * price_per_m_input) + (completion_tokens * price_per_m_output)
```

- [ ] **Step 2: 创建 app/prompts/skeleton.py**

```python
SYSTEM_PROMPT = """你是一位资深书籍分析专家。你的任务是从一本书的结构信息中提取知识骨架。
要求：
- 密度优先：每句话都要有信息量
- 实践者口吻：写"你可以用X方法做Y"，而不是"书中解释了X"
- 只分析非虚构/方法论类内容
- 忠实原文，不编造书中没有的概念"""

USER_PROMPT_TEMPLATE = """请根据以下信息提取本书知识骨架：

【书目录】
{toc}

【前言/导论】
{preface}

【各章首尾片段】
{chapter_glimpses}

请以 JSON 格式输出：
{{
  "thesis": "全书核心论点（100字内）",
  "distillable_score": 0.0-1.0（评估该书可蒸馏程度，小说/诗歌类接近0，方法论类接近1），
  "frameworks": [
    {{
      "name": "框架名称",
      "description": "一句话描述",
      "primary_chapter": "首次出现的章节号"
    }}
  ],
  "chapter_index": [
    {{
      "chapter_number": "章节号",
      "title": "章节标题",
      "summary": "一句话主题概括"
    }}
  ],
  "glossary": [
    {{
      "term": "术语",
      "definition": "简短定义（20字内）",
      "chapter": "所在章节"
    }}
  ]
}}

输出 6-10 个关键框架，术语表 10-20 条。"""
```

- [ ] **Step 3: 创建 app/prompts/chapter.py**

```python
SYSTEM_PROMPT = """你是一位书籍分析专家。请深入分析单个章节，提取可操作的知识。
要求：
- 密度优先：不要写废话，每句话都要传递有价值的信息
- 实践者口吻："当遇到X情况时，使用Y方法，因为Z"
- 不要复述原文，要提炼和重组
- 案例需保留"情境→做法→结果"三段结构"""

USER_PROMPT_TEMPLATE = """请分析以下章节：

章节编号：{chapter_number}
章节标题：{chapter_title}

【章节内容】
{chapter_content}

请以 JSON 格式输出：
{{
  "chapter_number": "{chapter_number}",
  "chapter_title": "{chapter_title}",
  "frameworks": ["本段提出的核心框架（如有），格式：框架名 — 一句话说明"],
  "methodologies": ["可操作的方法论/技巧，格式：方法名：具体做法"],
  "cases": ["书中的案例：情境 → 做法 → 结果"],
  "anti_patterns": ["反模式/常见误区：现象 → 原因 → 正确做法"],
  "actionable_steps": ["可直接执行的步骤清单"]
}}

如果没有某一项，返回空数组 []。每项最多 5 条。"""
```

- [ ] **Step 4: 创建 app/prompts/integrate.py**

```python
SYSTEM_PROMPT = """你是一位知识整合专家。你的任务是将分散的书中知识整合成一个连贯的整体。
要求：
- 合并跨章节的重复概念，保留最完整的版本
- 识别跨章节的逻辑链
- 按重要性排序
- 输出的 SKILL.md 内容要精炼、可执行"""

USER_PROMPT_TEMPLATE = """请整合以下知识并生成 SKILL.md 内容：

【全书骨架】
{skeleton_json}

【各章节分析结果】
{chapters_json}

请以 JSON 格式输出：
{{
  "merged_frameworks": [
    {{
      "name": "框架名",
      "description": "整合后的一段落描述",
      "related_chapters": ["章节1", "章节2"],
      "importance": 1-10
    }}
  ],
  "cross_chapter_links": [
    {{
      "from": "来源概念",
      "from_chapter": "章",
      "to": "目标概念",
      "to_chapter": "章",
      "relationship": "理论基础/延伸/对比/互补"
    }}
  ],
  "skill_md_content": "完整的 SKILL.md markdown 内容",
  "book_summary": "全书总结（200字内）",
  "knowledge_gaps": ["如有明显信息缺口，标注在此"]
}}
"""
```

- [ ] **Step 5: Commit**

```bash
git add app/ai_client.py app/prompts/
git commit -m "feat: add AI client with DeepSeek integration and prompt templates for stages 1-3"
```

---

### Task 7: Stage 1 — 骨架提取

**Files:**
- Create: `app/pipeline/stage1_skeleton.py`
- Create: `tests/test_stage1_skeleton.py`

- [ ] **Step 1: 创建 app/pipeline/stage1_skeleton.py**

```python
import json
from app.models import ChapterInfo, SkeletonOutput
from app.prompts.skeleton import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.ai_client import call_ai
from app.config import settings


def build_toc(chapters: list[ChapterInfo]) -> str:
    return "\n".join(f"- {c.number} {c.title}" for c in chapters)


def build_preface(full_text: str, max_chars: int = 2000) -> str:
    return full_text[:max_chars]


def build_chapter_glimpses(chapters: list[ChapterInfo], head_chars: int = 1000, tail_chars: int = 1000) -> str:
    lines = []
    for c in chapters:
        head = c.content[:head_chars]
        tail = c.content[-tail_chars:] if len(c.content) > tail_chars else ""
        lines.append(f"--- {c.number} {c.title} ---\n开头：{head}\n结尾：{tail}")
    return "\n\n".join(lines)


def run_skeleton_extraction(
    chapters: list[ChapterInfo],
    full_text: str,
) -> tuple[SkeletonOutput, int, int, float]:
    """提取全书骨架。返回 (SkeletonOutput, total_prompt_tokens, total_completion_tokens, cost)。"""
    toc = build_toc(chapters)
    preface = build_preface(full_text)
    glimpses = build_chapter_glimpses(chapters)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        toc=toc,
        preface=preface,
        chapter_glimpses=glimpses,
    )[:60000]  # 安全截断

    response_text, prompt_tokens, completion_tokens = call_ai(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=settings.DEEPSEEK_MODEL,
    )

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        data = _extract_json_from_text(response_text)

    skeleton = SkeletonOutput(
        thesis=data.get("thesis", ""),
        frameworks=data.get("frameworks", []),
        chapter_index=data.get("chapter_index", []),
        glossary=data.get("glossary", []),
        distillable_score=data.get("distillable_score", 0.5),
    )

    from app.ai_client import estimate_cost
    cost = estimate_cost(prompt_tokens, completion_tokens)

    return skeleton, prompt_tokens, completion_tokens, cost


def _extract_json_from_text(text: str) -> dict:
    """尝试从非纯 JSON 响应中提取 JSON 块。"""
    import re
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return {}
```

- [ ] **Step 2: 创建测试 tests/test_stage1_skeleton.py**

```python
import pytest
from app.pipeline.stage1_skeleton import build_toc, build_preface, build_chapter_glimpses
from app.models import ChapterInfo


def test_build_toc():
    chapters = [
        ChapterInfo(index=0, number="1", title="引言", content="...", char_count=10),
        ChapterInfo(index=1, number="2", title="方法", content="...", char_count=10),
    ]
    toc = build_toc(chapters)
    assert "1 引言" in toc
    assert "2 方法" in toc


def test_build_preface_truncates():
    text = "A" * 3000
    result = build_preface(text, max_chars=2000)
    assert len(result) == 2000


def test_build_chapter_glimpses():
    chapters = [
        ChapterInfo(
            index=0, number="1", title="测试",
            content="开头部分。" * 500 + "中间部分。" * 500 + "结尾部分。" * 500,
            char_count=6000,
        ),
    ]
    glimpses = build_chapter_glimpses(chapters, head_chars=500, tail_chars=500)
    assert "开头部分" in glimpses
    assert "结尾部分" in glimpses
    assert "1 测试" in glimpses


@pytest.mark.skipif(
    "not os.getenv('DEEPSEEK_API_KEY')",
    reason="需要 DEEPSEEK_API_KEY 环境变量",
)
def test_run_skeleton_extraction_integration():
    """集成测试：需要真实 API key。"""
    import os
    from app.pipeline.stage1_skeleton import run_skeleton_extraction

    chapters = [
        ChapterInfo(
            index=0, number="1", title="学习的方法",
            content="费曼技巧是一种通过教学来学习的方法。具体做法是：选择一个概念，尝试用最简单的语言解释它，如果卡住了就回去查阅资料。" * 100,
            char_count=5000,
        ),
        ChapterInfo(
            index=1, number="2", title="刻意练习",
            content="一万小时定律的核心是刻意练习，而不是简单的重复。刻意练习包括：明确目标、专注执行、即时反馈、突破舒适区。" * 100,
            char_count=5000,
        ),
    ]
    full_text = chapters[0].content + "\n" + chapters[1].content
    skeleton, prompt_tokens, completion_tokens, cost = run_skeleton_extraction(chapters, full_text)

    assert skeleton.thesis
    assert len(skeleton.frameworks) >= 2
    assert len(skeleton.chapter_index) >= 2
    assert cost > 0
```

- [ ] **Step 3: 运行单元测试**

```bash
python -m pytest tests/test_stage1_skeleton.py -v -k "not integration"
```

Expected: 3 pass

- [ ] **Step 4: Commit**

```bash
git add app/pipeline/stage1_skeleton.py tests/test_stage1_skeleton.py
git commit -m "feat: add stage1 skeleton extraction with TOC builder and chapter glimpse sampler"
```

---

### Task 8: Stage 2 — 并行章节蒸馏

**Files:**
- Create: `app/pipeline/stage2_chapters.py`
- Create: `tests/test_stage2_chapters.py`

- [ ] **Step 1: 创建 app/pipeline/stage2_chapters.py**

```python
import json
import asyncio
from app.models import ChapterInfo, ChapterOutput
from app.prompts.chapter import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.ai_client import call_ai
from app.config import settings


def _trim_chapter_content(content: str, head_chars: int = 8000, tail_chars: int = 8000) -> str:
    """截断章节内容，保留首尾。"""
    if len(content) <= head_chars + tail_chars:
        return content
    return content[:head_chars] + f"\n\n...（中间 {len(content) - head_chars - tail_chars} 字已省略）...\n\n" + content[-tail_chars:]


async def _process_one_chapter(chapter: ChapterInfo, semaphore: asyncio.Semaphore) -> tuple[ChapterOutput, int, int]:
    """处理单个章节（带并发控制）。"""
    async with semaphore:
        trimmed = _trim_chapter_content(chapter.content)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            chapter_number=chapter.number,
            chapter_title=chapter.title,
            chapter_content=trimmed,
        )

        response_text, prompt_tokens, completion_tokens = call_ai(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=settings.DEEPSEEK_LITE_MODEL,
        )

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            data = json.loads(match.group()) if match else {}

        output = ChapterOutput(
            chapter_number=data.get("chapter_number", chapter.number),
            chapter_title=data.get("chapter_title", chapter.title),
            frameworks=data.get("frameworks", []),
            methodologies=data.get("methodologies", []),
            cases=data.get("cases", []),
            anti_patterns=data.get("anti_patterns", []),
            actionable_steps=data.get("actionable_steps", []),
        )
        return output, prompt_tokens, completion_tokens


async def run_chapter_distillation(
    chapters: list[ChapterInfo],
    max_concurrent: int | None = None,
) -> tuple[list[ChapterOutput], int, int, float]:
    """并行蒸馏所有章节。返回 (输出列表, 总 prompt tokens, 总 completion tokens, 总成本)。"""
    if max_concurrent is None:
        max_concurrent = settings.MAX_CONCURRENT_CHAPTERS

    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [_process_one_chapter(c, semaphore) for c in chapters]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    outputs = []
    total_prompt = 0
    total_completion = 0

    for result in results:
        if isinstance(result, Exception):
            outputs.append(ChapterOutput(
                chapter_number="error",
                chapter_title=f"处理失败: {result}",
            ))
        else:
            output, p_tokens, c_tokens = result
            outputs.append(output)
            total_prompt += p_tokens
            total_completion += c_tokens

    from app.ai_client import estimate_cost
    cost = estimate_cost(total_prompt, total_completion, model=settings.DEEPSEEK_LITE_MODEL)

    return outputs, total_prompt, total_completion, cost
```

- [ ] **Step 2: 创建测试 tests/test_stage2_chapters.py**

```python
from app.pipeline.stage2_chapters import _trim_chapter_content


def test_trim_short_content_untouched():
    text = "短内容。" * 100
    result = _trim_chapter_content(text)
    assert result == text


def test_trim_long_content_truncates():
    text = "长内容。" * 5000
    result = _trim_chapter_content(text, head_chars=1000, tail_chars=1000)
    assert len(result) < len(text)
    assert "已省略" in result
    assert result.startswith("长内容。" * 250)
    assert result.endswith("长内容。" * 250)
```

- [ ] **Step 3: 运行测试**

```bash
python -m pytest tests/test_stage2_chapters.py -v
```

Expected: 2 pass

- [ ] **Step 4: Commit**

```bash
git add app/pipeline/stage2_chapters.py tests/test_stage2_chapters.py
git commit -m "feat: add stage2 parallel chapter distillation with semaphore-based concurrency"
```

---

### Task 9: Stage 3 & 4 — 知识整合 + 打包输出

**Files:**
- Create: `app/pipeline/stage3_integrate.py`, `app/pipeline/stage4_package.py`, `app/templates/SKILL.md.j2`, `app/templates/README.md.j2`
- Create: `tests/test_stage3_integrate.py`, `tests/test_stage4_package.py`

- [ ] **Step 1: 创建 app/pipeline/stage3_integrate.py**

```python
import json
from app.models import SkeletonOutput, ChapterOutput
from app.prompts.integrate import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.ai_client import call_ai
from app.config import settings


def run_integration(
    skeleton: SkeletonOutput,
    chapter_outputs: list[ChapterOutput],
) -> tuple[dict, int, int, float]:
    """整合知识。返回 (整合结果 dict, prompt_tokens, completion_tokens, cost)。"""
    skeleton_json = json.dumps(skeleton.model_dump(), ensure_ascii=False, indent=2)
    chapters_json = json.dumps(
        [c.model_dump() for c in chapter_outputs],
        ensure_ascii=False,
        indent=2,
    )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        skeleton_json=skeleton_json,
        chapters_json=chapters_json,
    )[:60000]

    response_text, prompt_tokens, completion_tokens = call_ai(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=settings.DEEPSEEK_MODEL,
    )

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        data = json.loads(match.group()) if match else {}

    from app.ai_client import estimate_cost
    cost = estimate_cost(prompt_tokens, completion_tokens)

    return data, prompt_tokens, completion_tokens, cost
```

- [ ] **Step 2: 创建 app/templates/SKILL.md.j2**

```jinja2
---
name: {{ title }}
description: 基于《{{ title }}》蒸馏的 AI 技能，可扮演作者思维、提供方法论指导、快速查阅书中精华
genre: non-fiction
---

# 本书核心
{{ thesis }}

# 关键框架
{% for f in frameworks %}
{{ loop.index }}. **{{ f.name }}** — {{ f.description }} (详见第{{ f.related_chapters | join('、') }}章)
{% endfor %}

# 章节索引
| 章节 | 主题 | 关键概念 |
|------|------|---------|
{% for ch in chapter_index %}
| {{ ch.chapter_number }} {{ ch.title }} | {{ ch.summary }} | — |
{% endfor %}

# 触发场景
{% for trigger in triggers %}
- {{ trigger }}
{% endfor %}

# 术语速查
| 术语 | 定义 | 详见 |
|------|------|------|
{% for term in glossary %}
| {{ term.term }} | {{ term.definition }} | 第{{ term.chapter }}章 |
{% endfor %}
```

- [ ] **Step 3: 创建 app/templates/README.md.j2**

```jinja2
# 《{{ title }}》Claude Code Skill

## 安装方法

将整个文件夹放入 `~/.claude/skills/` 目录：

```bash
cp -r "《{{ title }}》Skill" ~/.claude/skills/
```

## 使用场景

### 1. 扮演作者思维
```
/{{ slug }} 如何看待[某个问题]？
```

### 2. 学习方法论
```
/{{ slug }} 教我怎么用[书中的方法]
```

### 3. 快速查阅
```
/{{ slug }} [书中的概念]是什么？
```

### 4. 章节深入
```
/{{ slug }} 详细讲解第X章
```

## 文件说明

- `SKILL.md` — 核心心智模型，始终加载
- `chapters/` — 各章节详细分析，按需查阅
- `guides/` — 速查表和术语表

---

> 由 Book Skill Generator 自动生成
```

- [ ] **Step 4: 创建 app/pipeline/stage4_package.py**

```python
import zipfile
import shutil
from pathlib import Path
from jinja2 import Template
from app.config import settings


def build_skill_package(
    title: str,
    slug: str,
    thesis: str,
    frameworks: list[dict],
    chapter_index: list[dict],
    glossary: list[dict],
    triggers: list[str],
    chapter_outputs: list[dict],
    output_dir: Path | None = None,
) -> Path:
    """生成 Skill 文件包并打包为 zip。返回 zip 文件路径。"""
    base = output_dir or Path(settings.OUTPUT_DIR)
    work_dir = base / f"{slug}_skill"
    work_dir.mkdir(parents=True, exist_ok=True)

    # SKILL.md
    from jinja2 import Template
    import pkg_resources

    skill_tpl_path = Path(__file__).parent.parent / "templates" / "SKILL.md.j2"
    skill_template = Template(skill_tpl_path.read_text(encoding="utf-8"))
    skill_content = skill_template.render(
        title=title,
        thesis=thesis,
        frameworks=frameworks,
        chapter_index=chapter_index,
        glossary=glossary,
        triggers=triggers,
    )
    (work_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")

    # chapters/
    chapters_dir = work_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)
    for ch in chapter_outputs:
        ch_filename = f"{ch.get('chapter_number', 'unknown')}-{ch.get('chapter_title', 'untitled')}.md"
        ch_filename = "".join(c for c in ch_filename if c.isalnum() or c in ".-_")
        ch_path = chapters_dir / ch_filename
        ch_path.write_text(_format_chapter_md(ch), encoding="utf-8")

    # guides/
    guides_dir = work_dir / "guides"
    guides_dir.mkdir(exist_ok=True)
    if glossary:
        (guides_dir / "glossary.md").write_text(_format_glossary_md(glossary), encoding="utf-8")

    # README.md
    readme_tpl_path = Path(__file__).parent.parent / "templates" / "README.md.j2"
    readme_template = Template(readme_tpl_path.read_text(encoding="utf-8"))
    readme_content = readme_template.render(title=title, slug=slug)
    (work_dir / "README.md").write_text(readme_content, encoding="utf-8")

    # zip
    zip_path = base / f"{slug}_skill.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in work_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(base))

    # 清理工作目录
    shutil.rmtree(work_dir)

    return zip_path


def _format_chapter_md(ch: dict) -> str:
    lines = [f"# {ch.get('chapter_number', '?')} {ch.get('chapter_title', '')}", ""]
    if ch.get("frameworks"):
        lines.append("## 核心框架")
        for f in ch["frameworks"]:
            lines.append(f"- {f}")
        lines.append("")
    if ch.get("methodologies"):
        lines.append("## 方法论/技巧")
        for m in ch["methodologies"]:
            lines.append(f"- {m}")
        lines.append("")
    if ch.get("cases"):
        lines.append("## 书中案例")
        for c in ch["cases"]:
            lines.append(f"- {c}")
        lines.append("")
    if ch.get("anti_patterns"):
        lines.append("## 反模式/常见误区")
        for a in ch["anti_patterns"]:
            lines.append(f"- {a}")
        lines.append("")
    if ch.get("actionable_steps"):
        lines.append("## 可执行步骤")
        for s in ch["actionable_steps"]:
            lines.append(f"- {s}")
        lines.append("")
    return "\n".join(lines)


def _format_glossary_md(glossary: list[dict]) -> str:
    lines = ["# 术语表", "", "| 术语 | 定义 | 章节 |", "|------|------|------|"]
    for g in glossary:
        lines.append(f"| {g.get('term', '')} | {g.get('definition', '')} | {g.get('chapter', '')} |")
    return "\n".join(lines)
```

- [ ] **Step 5: 创建测试 tests/test_stage4_package.py**

```python
import zipfile
from pathlib import Path
from app.pipeline.stage4_package import build_skill_package


def test_build_skill_package_creates_zip(tmp_path):
    zip_path = build_skill_package(
        title="测试书",
        slug="test-book",
        thesis="这是一本关于测试的书。",
        frameworks=[
            {"name": "测试框架A", "description": "用于测试", "related_chapters": ["1"]},
        ],
        chapter_index=[
            {"chapter_number": "1", "title": "第一章", "summary": "介绍"},
        ],
        glossary=[
            {"term": "测试", "definition": "验证正确性", "chapter": "1"},
        ],
        triggers=["当用户问测试时 → 查阅第1章"],
        chapter_outputs=[
            {
                "chapter_number": "1",
                "chapter_title": "第一章",
                "frameworks": ["框架A：核心方法"],
                "methodologies": ["方法1：这样做"],
                "cases": ["某公司用了这个方法，效果很好"],
                "anti_patterns": ["不要只写不测"],
                "actionable_steps": ["1. 先写测试", "2. 再写代码"],
            },
        ],
        output_dir=tmp_path,
    )

    assert zip_path.exists()
    assert zip_path.suffix == ".zip"

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert any("SKILL.md" in n for n in names)
        assert any("chapters/" in n for n in names)
        assert any("README.md" in n for n in names)
        assert any("glossary.md" in n for n in names)


def test_build_skill_package_no_glossary(tmp_path):
    zip_path = build_skill_package(
        title="测试书2",
        slug="test-book-2",
        thesis="测试。",
        frameworks=[],
        chapter_index=[],
        glossary=[],
        triggers=[],
        chapter_outputs=[],
        output_dir=tmp_path,
    )
    assert zip_path.exists()
```

- [ ] **Step 6: 运行测试**

```bash
python -m pytest tests/test_stage4_package.py -v
```

Expected: 2 pass

- [ ] **Step 7: Commit**

```bash
git add app/pipeline/stage3_integrate.py app/pipeline/stage4_package.py app/templates/ tests/test_stage3_integrate.py tests/test_stage4_package.py
git commit -m "feat: add stage3 knowledge integration, stage4 package output, and Jinja2 templates"
```

---

### Task 10: 管线编排器 + 端到端集成测试

**Files:**
- Create: `app/pipeline/runner.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: 创建 app/pipeline/runner.py**

```python
import asyncio
import time
from pathlib import Path
from app.pipeline.stage0_extract import extract
from app.pipeline.stage1_skeleton import run_skeleton_extraction
from app.pipeline.stage2_chapters import run_chapter_distillation
from app.pipeline.stage3_integrate import run_integration
from app.pipeline.stage4_package import build_skill_package
from app.models import PipelineResult
from app.config import settings


async def run_pipeline(filepath: Path) -> PipelineResult:
    """完整管线：上传文件 → 蒸馏 → 打包。"""
    start_time = time.time()
    total_tokens = 0
    total_cost = 0.0
    errors = []

    output_dir = Path(settings.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage 0: Extract
    try:
        meta, chapters, full_text = extract(filepath)
        total_chars = meta.total_chars
    except Exception as e:
        return PipelineResult(
            success=False,
            errors=[f"Stage 0 失败: {e}"],
            elapsed_seconds=time.time() - start_time,
        )

    # 检查可蒸馏度
    if meta.format.value in ("epub", "pdf") and total_chars > 1000000:
        errors.append(f"警告：文件过大（{total_chars} 字符），处理时间可能较长")

    # Stage 1: Skeleton
    try:
        skeleton, p_t, c_t, cost = run_skeleton_extraction(chapters, full_text)
        total_tokens += p_t + c_t
        total_cost += cost

        if skeleton.distillable_score < 0.3:
            return PipelineResult(
                success=False,
                errors=[f"该书可蒸馏度评分过低（{skeleton.distillable_score:.1f}），可能不适合蒸馏。小说、诗歌等类型暂不支持。"],
                total_tokens=total_tokens,
                total_cost=total_cost,
                elapsed_seconds=time.time() - start_time,
            )
    except Exception as e:
        return PipelineResult(
            success=False,
            errors=[f"Stage 1 骨架提取失败: {e}"],
            total_tokens=total_tokens,
            total_cost=total_cost,
            elapsed_seconds=time.time() - start_time,
        )

    # Stage 2: Chapters
    try:
        chapter_outputs, p_t, c_t, cost = await run_chapter_distillation(chapters)
        total_tokens += p_t + c_t
        total_cost += cost
    except Exception as e:
        errors.append(f"Stage 2 部分章节失败: {e}")
        chapter_outputs = []

    if not chapter_outputs:
        return PipelineResult(
            success=False,
            errors=errors + ["Stage 2 未产出任何章节结果"],
            total_tokens=total_tokens,
            total_cost=total_cost,
            elapsed_seconds=time.time() - start_time,
        )

    # Stage 3: Integration
    try:
        integrated, p_t, c_t, cost = run_integration(skeleton, chapter_outputs)
        total_tokens += p_t + c_t
        total_cost += cost
    except Exception as e:
        errors.append(f"Stage 3 整合失败: {e}")
        integrated = {"skill_md_content": "", "merged_frameworks": [], "cross_chapter_links": [], "book_summary": "", "knowledge_gaps": []}

    # Stage 4: Package
    try:
        title = meta.title or filepath.stem
        slug = "".join(c for c in title if c.isalnum() or c in "_- ")[:30].strip().replace(" ", "-").lower()

        triggers = [
            f"当用户询问关于{topic}的问题时 → 查阅相关章节"
            for topic in [f["name"] for f in integrated.get("merged_frameworks", [])[:5]]
        ]

        zip_path = build_skill_package(
            title=title,
            slug=slug,
            thesis=skeleton.thesis,
            frameworks=integrated.get("merged_frameworks", []),
            chapter_index=skeleton.chapter_index,
            glossary=skeleton.glossary,
            triggers=triggers or ["当用户询问书中内容时 → 查阅章节索引"],
            chapter_outputs=[c.model_dump() for c in chapter_outputs],
            output_dir=output_dir,
        )
    except Exception as e:
        return PipelineResult(
            success=False,
            errors=errors + [f"Stage 4 打包失败: {e}"],
            total_tokens=total_tokens,
            total_cost=total_cost,
            elapsed_seconds=time.time() - start_time,
        )

    elapsed = time.time() - start_time

    return PipelineResult(
        success=True,
        zip_path=str(zip_path),
        total_tokens=total_tokens,
        total_cost=round(total_cost, 4),
        elapsed_seconds=round(elapsed, 1),
        errors=errors,
    )
```

- [ ] **Step 2: 创建端到端测试 tests/test_runner.py**

```python
import pytest
from pathlib import Path
from app.pipeline.runner import run_pipeline
from app.models import PipelineResult


@pytest.mark.asyncio
@pytest.mark.skipif(
    "not os.getenv('DEEPSEEK_API_KEY')",
    reason="需要 DEEPSEEK_API_KEY 环境变量",
)
async def test_run_pipeline_with_txt(sample_txt):
    result = await run_pipeline(Path(str(sample_txt)))
    assert isinstance(result, PipelineResult)
    assert result.success
    assert result.total_tokens > 0
    assert result.total_cost > 0
    assert result.elapsed_seconds > 0
    if result.zip_path:
        assert Path(result.zip_path).exists()
        print(f"\n  Cost: ¥{result.total_cost:.4f}")
        print(f"  Tokens: {result.total_tokens}")
        print(f"  Time: {result.elapsed_seconds}s")
        print(f"  Zip: {result.zip_path}")
```

- [ ] **Step 3: 找一个真实 TXT 书做手动测试**

```bash
# 下载一本免费中文书做测试
# 用《论语》或其他公版书的 txt 版本
```

- [ ] **Step 4: Commit**

```bash
git add app/pipeline/runner.py tests/test_runner.py
git commit -m "feat: add pipeline orchestrator with end-to-end flow and distillability check"
```

---

## Phase 2: Web 应用

### Task 11: FastAPI 后端 + 文件上传/下载

**Files:**
- Create: `app/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: 创建 app/main.py**

```python
import asyncio
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.pipeline.runner import run_pipeline

app = FastAPI(title="Book Skill Generator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>Book Skill Generator</h1>"


@app.post("/api/upload")
async def upload_book(file: UploadFile = File(...)):
    """上传并处理书籍文件。"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".pdf", ".epub", ".txt", ".md"):
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {suffix}")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex[:8]
    save_path = upload_dir / f"{file_id}_{file.filename}"
    content = await file.read()

    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"文件超过最大限制 {settings.MAX_FILE_SIZE_MB}MB")

    save_path.write_bytes(content)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "status": "uploaded",
    }


@app.get("/api/download/{file_path:path}")
async def download_result(file_path: str):
    """下载处理完成的 zip 文件。"""
    full_path = Path(file_path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在或已过期")
    return FileResponse(
        path=str(full_path),
        filename=full_path.name,
        media_type="application/zip",
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 2: 创建测试 tests/test_main.py**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_invalid_format():
    response = client.post("/api/upload", files={"file": ("test.doc", b"content", "application/octet-stream")})
    assert response.status_code == 400
    assert "不支持" in response.json()["detail"]


def test_upload_txt():
    response = client.post("/api/upload", files={"file": ("test.txt", b"hello world", "text/plain")})
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["status"] == "uploaded"
    assert "file_id" in data


def test_upload_file_too_large():
    big_content = b"x" * (51 * 1024 * 1024)
    response = client.post("/api/upload", files={"file": ("big.txt", big_content, "text/plain")})
    assert response.status_code == 400


def test_download_not_found():
    response = client.get("/api/download/nonexistent.zip")
    assert response.status_code == 404


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
```

- [ ] **Step 3: 运行测试**

```bash
python -m pytest tests/test_main.py -v
```

Expected: 6 pass

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: add FastAPI backend with upload, download, and health endpoints"
```

---

### Task 12: SSE 进度推送 + 蒸馏处理端点

**Files:**
- Modify: `app/main.py` — 添加 SSE 端点

- [ ] **Step 1: 在 app/main.py 添加 SSE 蒸馏端点**

```python
# 在现有 import 后添加
import json
import asyncio
import time
from pathlib import Path
from sse_starlette.sse import EventSourceResponse
from app.pipeline.stage0_extract import extract
from app.pipeline.stage1_skeleton import run_skeleton_extraction
from app.pipeline.stage2_chapters import run_chapter_distillation
from app.pipeline.stage3_integrate import run_integration
from app.pipeline.stage4_package import build_skill_package


async def _event_generator(filepath: Path):
    """SSE 事件生成器，逐步推进管线并推送进度。"""
    start_time = time.time()
    total_tokens = 0
    total_cost = 0.0

    yield {"event": "progress", "data": json.dumps({
        "stage": "stage0", "message": "正在解析文件...", "percent": 0,
    }, ensure_ascii=False)}

    meta, chapters, full_text = extract(filepath)

    yield {"event": "progress", "data": json.dumps({
        "stage": "stage0", "message": f"解析完成：{meta.total_chars} 字符，{len(chapters)} 个章节",
        "percent": 10, "detail": f"格式: {meta.format.value}",
    }, ensure_ascii=False)}

    if meta.total_chars > 1000000:
        yield {"event": "progress", "data": json.dumps({
            "stage": "warning", "message": f"文件较大（{meta.total_chars} 字符），处理可能需要几分钟",
            "percent": 10,
        }, ensure_ascii=False)}

    yield {"event": "progress", "data": json.dumps({
        "stage": "stage1", "message": "正在提取全书骨架...", "percent": 15,
    }, ensure_ascii=False)}

    skeleton, p_t, c_t, cost = run_skeleton_extraction(chapters, full_text)
    total_tokens += p_t + c_t
    total_cost += cost

    yield {"event": "progress", "data": json.dumps({
        "stage": "stage1", "message": f"骨架提取完成：{len(skeleton.frameworks)} 个框架",
        "percent": 30, "detail": f"核心论点: {skeleton.thesis[:50]}...",
    }, ensure_ascii=False)}

    if skeleton.distillable_score < 0.3:
        yield {"event": "error", "data": json.dumps({
            "message": f"该书可蒸馏度评分过低（{skeleton.distillable_score:.1f}），可能不适合蒸馏",
        }, ensure_ascii=False)}
        return

    yield {"event": "progress", "data": json.dumps({
        "stage": "stage2", "message": f"正在蒸馏章节 (0/{len(chapters)})...", "percent": 30,
    }, ensure_ascii=False)}

    chapter_outputs, p_t, c_t, cost = await run_chapter_distillation(chapters)
    total_tokens += p_t + c_t
    total_cost += cost

    yield {"event": "progress", "data": json.dumps({
        "stage": "stage2", "message": f"章节蒸馏完成：{len(chapter_outputs)}/{len(chapters)} 章成功",
        "percent": 60,
    }, ensure_ascii=False)}

    yield {"event": "progress", "data": json.dumps({
        "stage": "stage3", "message": "正在整合知识...", "percent": 70,
    }, ensure_ascii=False)}

    integrated, p_t, c_t, cost = run_integration(skeleton, chapter_outputs)
    total_tokens += p_t + c_t
    total_cost += cost

    yield {"event": "progress", "data": json.dumps({
        "stage": "stage3", "message": "知识整合完成",
        "percent": 85,
    }, ensure_ascii=False)}

    yield {"event": "progress", "data": json.dumps({
        "stage": "stage4", "message": "正在打包...", "percent": 90,
    }, ensure_ascii=False)}

    title = meta.title or filepath.stem
    slug = "".join(c for c in title if c.isalnum() or c in "_- ")[:30].strip().replace(" ", "-").lower()
    triggers = [
        f"当用户询问关于{topic}的问题时 → 查阅相关章节"
        for topic in [f["name"] for f in integrated.get("merged_frameworks", [])[:5]]
    ]

    output_dir = Path(settings.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = build_skill_package(
        title=title, slug=slug,
        thesis=skeleton.thesis,
        frameworks=integrated.get("merged_frameworks", []),
        chapter_index=skeleton.chapter_index,
        glossary=skeleton.glossary,
        triggers=triggers or ["当用户询问书中内容时 → 查阅章节索引"],
        chapter_outputs=[c.model_dump() for c in chapter_outputs],
        output_dir=output_dir,
    )

    elapsed = time.time() - start_time

    yield {"event": "complete", "data": json.dumps({
        "message": "蒸馏完成！",
        "percent": 100,
        "zip_filename": zip_path.name,
        "download_path": str(zip_path),
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 4),
        "elapsed_seconds": round(elapsed, 1),
    }, ensure_ascii=False)}


@app.post("/api/distill/{file_id}")
async def distill_book(file_id: str):
    """SSE 端点：开始蒸馏并推送实时进度。"""
    upload_dir = Path(settings.UPLOAD_DIR)
    files = list(upload_dir.glob(f"{file_id}_*"))
    if not files:
        raise HTTPException(status_code=404, detail="文件未找到，请重新上传")

    filepath = files[0]
    return EventSourceResponse(_event_generator(filepath))
```

- [ ] **Step 2: 追加测试到 tests/test_main.py**

```python
def test_distill_file_not_found():
    response = client.post("/api/distill/nonexistent")
    assert response.status_code == 404
```

- [ ] **Step 3: 运行测试**

```bash
python -m pytest tests/test_main.py -v
```

Expected: 7 pass

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: add SSE distillation endpoint with real-time progress streaming"
```

---

### Task 13: 前端页面

**Files:**
- Create: `app/static/index.html`, `app/static/style.css`

- [ ] **Step 1: 创建 app/static/style.css**

略（开发时让 Codex 写）

- [ ] **Step 2: 创建 app/static/index.html**

略（开发时让 Codex 写，关键功能：拖拽上传、配置面板、SSE 进度展示、下载按钮）

---

## Phase 3: 打磨上线

### Task 14: 错误处理 + 重试机制

在 `ai_client.py` 的 `call_ai` 函数中添加指数退避重试逻辑，管线各阶段检查返回值有效性。

### Task 15: Docker 部署

编写 `Dockerfile` 和 `docker-compose.yml`，确保 `source venv/bin/activate` 不是必需的。

### Task 16: 12 本书质量测试

用 12 本真实书籍做端到端测试，记录成本、时间、输出质量，调优 Prompt。

---

## 附录：开发环境准备

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
```

## 附录：运行方式

```bash
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
