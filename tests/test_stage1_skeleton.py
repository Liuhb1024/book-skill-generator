from pathlib import Path

import pytest

from app.config import settings
from app.pipeline.stage0_extract import extract
from app.pipeline.stage1_skeleton import (
    build_chapter_glimpses,
    build_preface,
    build_toc,
    run_skeleton_extraction,
)


def test_build_toc():
    _, chapters, _ = extract(Path("test_fixtures/sample.txt"))

    toc = build_toc(chapters)

    assert "[一] 为什么学习" in toc
    assert "[二] 如何学习" in toc


def test_build_preface():
    preface = build_preface("abcdef", max_chars=3)

    assert preface == "abc"


def test_build_chapter_glimpses():
    _, chapters, _ = extract(Path("test_fixtures/sample.txt"))

    glimpses = build_chapter_glimpses(chapters, head_chars=20, tail_chars=20)

    assert "为什么学习" in glimpses
    assert "如何学习" in glimpses
    assert "首部" in glimpses
    assert "尾部" in glimpses


@pytest.mark.skipif(not settings.DEEPSEEK_API_KEY, reason="DEEPSEEK_API_KEY not configured")
def test_run_skeleton_extraction_integration():
    _, chapters, full_text = extract(Path("test_fixtures/sample.txt"))

    skeleton, prompt_tokens, completion_tokens, cost = run_skeleton_extraction(chapters, full_text)

    assert skeleton.thesis
    assert len(skeleton.frameworks) >= 2
    assert len(skeleton.chapter_index) >= 2
    assert prompt_tokens > 0
    assert completion_tokens > 0
    assert cost > 0
