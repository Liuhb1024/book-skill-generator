import pytest

from app.config import settings
from app.pipeline.stage3_integrate import run_integration


@pytest.mark.skipif(not settings.DEEPSEEK_API_KEY, reason="DEEPSEEK_API_KEY not configured")
def test_run_integration_integration():
    spine_md = """# 《测试书》知识骨架

## 全书核心论点
高效学习来自元认知、刻意练习和可执行方法的结合。

## 核心框架（6-10个）
### 元认知循环
- **是什么**：计划、监控、复盘学习过程
- **何时用**：面对复杂学习任务时
- **怎么用**：设定目标、观察反馈、调整策略
- **首次出现**：第一章

## 可蒸馏度评估
- 评分：0.9
- 理由：方法明确。
"""
    chapter_mds = [
        ("01", "为什么学习", "# 第一章：为什么学习\n\n## 核心要旨\n元认知是学习效率的关键。\n", 10, 5),
        ("02", "如何学习", "# 第二章：如何学习\n\n## 核心要旨\n费曼技巧帮助检验理解。\n", 10, 5),
    ]

    skill_md, prompt_tokens, completion_tokens, cost = run_integration(
        spine_md,
        chapter_mds,
        book_title="测试书",
        author="未知",
        slug="test-book",
    )

    assert skill_md.startswith("---")
    assert "allowed-tools: Read" in skill_md
    assert "## 如何使用这个 Skill" in skill_md
    assert "## 主题索引" in skill_md
    assert "chapter_number" not in skill_md
    assert prompt_tokens > 0
    assert completion_tokens > 0
    assert cost > 0
