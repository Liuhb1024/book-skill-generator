import json
import re

from app.ai_client import call_ai, estimate_cost
from app.config import settings
from app.models import ChapterInfo, SkeletonOutput
from app.prompts.skeleton import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


def build_toc(chapters: list[ChapterInfo]) -> str:
    return "\n".join(f"[{chapter.number}] {chapter.title}" for chapter in chapters)


def build_preface(full_text: str, max_chars: int = 2000) -> str:
    return full_text[:max_chars]


def build_chapter_glimpses(
    chapters: list[ChapterInfo],
    head_chars: int = 1000,
    tail_chars: int = 1000,
) -> str:
    glimpses = []
    for chapter in chapters:
        head = chapter.content[:head_chars]
        tail = chapter.content[-tail_chars:] if tail_chars > 0 else ""
        glimpses.append(
            f"[{chapter.number}] {chapter.title}\n"
            f"首部:\n{head}\n"
            f"尾部:\n{tail}"
        )
    return "\n\n".join(glimpses)


def run_skeleton_extraction(
    chapters: list[ChapterInfo],
    full_text: str,
) -> tuple[SkeletonOutput, int, int, float]:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        toc=build_toc(chapters),
        preface=build_preface(full_text),
        chapter_glimpses=build_chapter_glimpses(chapters),
    )
    content, prompt_tokens, completion_tokens = call_ai(
        SYSTEM_PROMPT,
        user_prompt,
        model=settings.SKELETON_MODEL,
        temperature=0.3,
        response_format="json_object",
        max_tokens=4096,
    )
    payload = _normalize_skeleton_payload(_parse_json_object(content))
    skeleton = SkeletonOutput.model_validate(payload)
    cost = estimate_cost(prompt_tokens, completion_tokens, model=settings.SKELETON_MODEL)
    return skeleton, prompt_tokens, completion_tokens, cost


def _parse_json_object(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _normalize_skeleton_payload(payload: dict) -> dict:
    frameworks = payload.get("frameworks")
    if isinstance(frameworks, list):
        payload["frameworks"] = [
            item if isinstance(item, dict) else {"name": str(item)}
            for item in frameworks
        ]

    chapter_index = payload.get("chapter_index")
    if isinstance(chapter_index, dict):
        payload["chapter_index"] = [
            {"chapter": key, **value} if isinstance(value, dict) else {"chapter": key, "summary": str(value)}
            for key, value in chapter_index.items()
        ]

    glossary = payload.get("glossary")
    if isinstance(glossary, dict):
        payload["glossary"] = [
            {"term": key, "definition": str(value)}
            for key, value in glossary.items()
        ]
    elif isinstance(glossary, list):
        payload["glossary"] = [
            item if isinstance(item, dict) else {"term": str(item), "definition": ""}
            for item in glossary
        ]
    return payload
