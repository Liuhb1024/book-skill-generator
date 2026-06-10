import asyncio
import json
import re

from app.ai_client import call_ai, estimate_cost
from app.config import settings
from app.models import ChapterInfo, ChapterOutput
from app.prompts.chapter import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


def _trim_chapter_content(
    content: str,
    head_chars: int = 8000,
    tail_chars: int = 8000,
) -> str:
    if len(content) <= head_chars + tail_chars:
        return content

    omitted = len(content) - head_chars - tail_chars
    return (
        f"{content[:head_chars]}\n\n"
        f"... 省略 {omitted} 字 ...\n\n"
        f"{content[-tail_chars:]}"
    )


async def run_chapter_distillation(
    chapters: list[ChapterInfo],
    max_concurrent: int = 10,
) -> tuple[list[ChapterOutput], int, int, float]:
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [_process_one_chapter(chapter, semaphore) for chapter in chapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0

    for chapter, result in zip(chapters, results):
        if isinstance(result, Exception):
            outputs.append(_failed_chapter_output(chapter, result))
            continue

        output, prompt_tokens, completion_tokens, cost = result
        outputs.append(output)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost

    return outputs, total_prompt_tokens, total_completion_tokens, round(total_cost, 6)


async def _process_one_chapter(
    chapter: ChapterInfo,
    semaphore: asyncio.Semaphore,
) -> tuple[ChapterOutput, int, int, float]:
    async with semaphore:
        try:
            user_prompt = USER_PROMPT_TEMPLATE.format(
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                chapter_content=_trim_chapter_content(chapter.content),
            )
            content, prompt_tokens, completion_tokens = await asyncio.to_thread(
                call_ai,
                SYSTEM_PROMPT,
                user_prompt,
                model=settings.CHAPTER_MODEL,
                temperature=0.3,
                response_format="json_object",
                max_tokens=4096,
            )
            payload = _normalize_chapter_payload(_parse_json_object(content), chapter)
            output = ChapterOutput.model_validate(payload)
            cost = estimate_cost(prompt_tokens, completion_tokens, model=settings.CHAPTER_MODEL)
            return output, prompt_tokens, completion_tokens, cost
        except Exception as exc:
            return _failed_chapter_output(chapter, exc), 0, 0, 0.0


def _failed_chapter_output(chapter: ChapterInfo, exc: Exception) -> ChapterOutput:
    return ChapterOutput(
        chapter_number=chapter.number,
        chapter_title=chapter.title,
        anti_patterns=[f"处理失败: {exc}"],
    )


def _parse_json_object(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _normalize_chapter_payload(payload: dict, chapter: ChapterInfo) -> dict:
    payload.setdefault("chapter_number", chapter.number)
    payload.setdefault("chapter_title", chapter.title)
    for key in ("frameworks", "methodologies", "cases", "anti_patterns", "actionable_steps"):
        payload[key] = _normalize_string_list(payload.get(key))
    return payload


def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [
            json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)
            for item in value
        ]
    if isinstance(value, dict):
        return [f"{key}: {item}" for key, item in value.items()]
    return [str(value)]
