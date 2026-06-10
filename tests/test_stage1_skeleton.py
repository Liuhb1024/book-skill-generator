from pathlib import Path

import pytest

from app.config import settings
from app.pipeline.stage0_extract import extract
from app.pipeline.stage1_skeleton import (
    build_chapter_glimpses,
    build_preface,
    build_toc,
    extract_distillable_score,
    run_skeleton_extraction,
)


def test_build_toc():
    _, chapters, _ = extract(Path("test_fixtures/sample.txt"))

    toc = build_toc(chapters)

    assert "[一] 为什么学习" in toc
    assert "[二] 如何学习" in toc


def test_build_preface():
    assert build_preface("abcdef", max_chars=3) == "abc"


def test_build_chapter_glimpses():
    _, chapters, _ = extract(Path("test_fixtures/sample.txt"))

    glimpses = build_chapter_glimpses(chapters, head_chars=20, tail_chars=20)

    assert "为什么学习" in glimpses
    assert "如何学习" in glimpses
    assert "首部" in glimpses
    assert "尾部" in glimpses


def test_extract_distillable_score():
    assert extract_distillable_score("## 可蒸馏度评估\n- 评分：0.72\n- 理由：可操作") == 0.72


@pytest.mark.skipif(not settings.DEEPSEEK_API_KEY, reason="DEEPSEEK_API_KEY not configured")
def test_run_skeleton_extraction_integration():
    _, chapters, full_text = extract(Path("test_fixtures/sample.txt"))

    spine_md, prompt_tokens, completion_tokens, cost = run_skeleton_extraction(chapters, full_text, "sample")

    assert "# 《sample》知识骨架" in spine_md
    assert "## 全书核心论点" in spine_md
    assert "## 核心框架" in spine_md
    assert prompt_tokens > 0
    assert completion_tokens > 0
    assert cost > 0
