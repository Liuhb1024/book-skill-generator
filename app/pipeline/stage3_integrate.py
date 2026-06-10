import json
import re

from app.ai_client import call_ai, estimate_cost
from app.config import settings
from app.models import ChapterOutput, SkeletonOutput
from app.prompts.integrate import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


def run_integration(
    skeleton: SkeletonOutput,
    chapter_outputs: list[ChapterOutput],
) -> tuple[dict, int, int, float]:
    skeleton_json = json.dumps(skeleton.model_dump(), ensure_ascii=False)
    chapters_json = json.dumps(
        [chapter.model_dump() for chapter in chapter_outputs],
        ensure_ascii=False,
    )
    user_prompt = USER_PROMPT_TEMPLATE.format(
        skeleton_json=skeleton_json,
        chapters_json=chapters_json,
    )
    user_prompt += (
        "\n\n请确保输出 JSON 至少包含 merged_frameworks 和 skill_md_content 两个非空字段。"
        "merged_frameworks 应为整合后的框架列表，skill_md_content 应为可直接写入 SKILL.md 的 Markdown 内容。"
    )

    content, prompt_tokens, completion_tokens = call_ai(
        SYSTEM_PROMPT,
        user_prompt,
        model=settings.INTEGRATE_MODEL,
        temperature=0.3,
        response_format="json_object",
        max_tokens=4096,
    )
    result = _normalize_integration_result(
        _parse_json_object(content),
        skeleton,
        chapter_outputs,
    )
    cost = estimate_cost(prompt_tokens, completion_tokens, model=settings.INTEGRATE_MODEL)
    return result, prompt_tokens, completion_tokens, cost


def _parse_json_object(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _normalize_integration_result(
    result: dict,
    skeleton: SkeletonOutput,
    chapter_outputs: list[ChapterOutput],
) -> dict:
    if not result.get("merged_frameworks"):
        result["merged_frameworks"] = skeleton.frameworks or [
            {"name": item}
            for chapter in chapter_outputs
            for item in chapter.frameworks
        ]

    if not result.get("skill_md_content"):
        framework_lines = []
        for item in result["merged_frameworks"]:
            if isinstance(item, dict):
                framework_lines.append(f"- {item.get('name') or item.get('title') or item}")
            else:
                framework_lines.append(f"- {item}")
        result["skill_md_content"] = "\n".join(
            [
                "# 本书核心",
                skeleton.thesis,
                "",
                "## 关键框架",
                *framework_lines,
            ]
        ).strip()

    return result
