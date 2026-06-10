import asyncio
from pathlib import Path

import pytest

from app.config import settings
from app.pipeline.stage0_extract import extract
from app.pipeline.stage2_chapters import _has_repetition_loop, _trim_chapter_content, run_chapter_distillation


def test_trim_short_content():
    content = "短内容"

    assert _trim_chapter_content(content) == content


def test_trim_long_content():
    content = "A" * 9000 + "B" * 9000

    trimmed = _trim_chapter_content(content, head_chars=8000, tail_chars=8000)

    assert trimmed.startswith("A" * 8000)
    assert trimmed.endswith("B" * 8000)
    assert "省略" in trimmed
    assert len(trimmed) < len(content)


def test_has_repetition_loop_detects_char_repeat():
    assert _has_repetition_loop("正常文本" + "夫" * 15) is True


def test_has_repetition_loop_detects_bigram_repeat():
    assert _has_repetition_loop("前面内容" + "你好" * 10) is True
    assert _has_repetition_loop("这是一段正常的章节蒸馏内容，包含多个框架和概念。") is False


@pytest.mark.skipif(not settings.DEEPSEEK_API_KEY, reason="DEEPSEEK_API_KEY not configured")
def test_run_chapter_distillation_integration():
    _, chapters, _ = extract(Path("test_fixtures/sample.txt"))

    outputs, prompt_tokens, completion_tokens, cost = asyncio.run(
        run_chapter_distillation(chapters, max_concurrent=2)
    )

    assert len(outputs) == 2
    assert all("## 核心要旨" in output[2] for output in outputs)
    assert all("chapter_number" not in output[2] for output in outputs)
    assert prompt_tokens > 0
    assert completion_tokens > 0
    assert cost > 0
