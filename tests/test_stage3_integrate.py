import pytest

from app.config import settings
from app.models import ChapterOutput, SkeletonOutput
from app.pipeline.stage3_integrate import run_integration


@pytest.mark.skipif(not settings.DEEPSEEK_API_KEY, reason="DEEPSEEK_API_KEY not configured")
def test_run_integration_integration():
    skeleton = SkeletonOutput(
        thesis="高效学习来自元认知、刻意练习和可执行方法的结合。",
        frameworks=[
            {"name": "元认知循环", "description": "计划、监控、复盘学习过程", "related_chapters": ["一"]},
            {"name": "费曼技巧", "description": "用自己的话解释概念以检验理解", "related_chapters": ["二"]},
        ],
        chapter_index=[
            {"chapter_number": "一", "title": "为什么学习", "summary": "解释学习本质与元认知。"},
            {"chapter_number": "二", "title": "如何学习", "summary": "介绍费曼技巧和番茄工作法。"},
        ],
        glossary=[
            {"term": "元认知", "definition": "对自己思维过程的理解和控制", "chapter": "一"},
        ],
    )
    chapter_outputs = [
        ChapterOutput(
            chapter_number="一",
            chapter_title="为什么学习",
            frameworks=["元认知循环"],
            methodologies=["间隔重复"],
            actionable_steps=["为学习任务设置反馈点"],
        ),
        ChapterOutput(
            chapter_number="二",
            chapter_title="如何学习",
            frameworks=["费曼技巧"],
            methodologies=["番茄工作法"],
            actionable_steps=["用自己的话解释概念"],
        ),
    ]

    result, prompt_tokens, completion_tokens, cost = run_integration(skeleton, chapter_outputs)

    assert result["merged_frameworks"]
    assert result["skill_md_content"]
    assert prompt_tokens > 0
    assert completion_tokens > 0
    assert cost > 0
