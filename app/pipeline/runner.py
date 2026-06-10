import re
import time
from pathlib import Path

from app.models import ChapterOutput, PipelineResult
from app.pipeline.stage0_extract import extract
from app.pipeline.stage1_skeleton import run_skeleton_extraction
from app.pipeline.stage2_chapters import run_chapter_distillation
from app.pipeline.stage3_integrate import run_integration
from app.pipeline.stage4_package import build_skill_package


PINYIN_MAP = {
    "测": "ce",
    "试": "shi",
    "书": "shu",
    "学": "xue",
    "习": "xi",
    "方": "fang",
    "法": "fa",
    "为": "wei",
    "什": "shen",
    "么": "me",
    "如": "ru",
    "何": "he",
    "科": "ke",
    "本": "ben",
    "核": "he",
    "心": "xin",
}


async def run_pipeline(filepath: Path) -> PipelineResult:
    start = time.monotonic()
    errors: list[str] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0

    try:
        meta, chapters, full_text = extract(filepath)
    except Exception as exc:
        return _result(
            success=False,
            start=start,
            errors=[f"Stage 0 extract failed: {exc}"],
        )

    title = meta.title or filepath.stem
    slug = make_slug(title)

    try:
        skeleton, prompt_tokens, completion_tokens, cost = run_skeleton_extraction(chapters, full_text)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost
    except Exception as exc:
        return _result(
            success=False,
            start=start,
            errors=errors + [f"Stage 1 skeleton failed: {exc}"],
        )

    if skeleton.distillable_score < 0.3:
        return _result(
            success=False,
            start=start,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            total_cost=total_cost,
            errors=errors + [f"Distillable score too low: {skeleton.distillable_score}"],
        )

    try:
        chapter_outputs, prompt_tokens, completion_tokens, cost = await run_chapter_distillation(chapters)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost
    except Exception as exc:
        errors.append(f"Stage 2 chapter distillation failed: {exc}")
        chapter_outputs = [
            ChapterOutput(chapter_number=chapter.number, chapter_title=chapter.title)
            for chapter in chapters
        ]

    try:
        integrated, prompt_tokens, completion_tokens, cost = run_integration(skeleton, chapter_outputs)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost
    except Exception as exc:
        errors.append(f"Stage 3 integration failed: {exc}")
        integrated = {}

    try:
        zip_path = build_skill_package(
            title=title,
            slug=slug,
            thesis=integrated.get("thesis") or skeleton.thesis,
            frameworks=_pick_frameworks(integrated, skeleton),
            chapter_index=_pick_chapter_index(integrated, skeleton),
            glossary=_pick_glossary(integrated, skeleton),
            triggers=_pick_triggers(integrated),
            chapter_outputs=chapter_outputs,
        )
    except Exception as exc:
        return _result(
            success=False,
            start=start,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            total_cost=total_cost,
            errors=errors + [f"Stage 4 packaging failed: {exc}"],
        )

    return _result(
        success=True,
        start=start,
        zip_path=zip_path,
        total_tokens=total_prompt_tokens + total_completion_tokens,
        total_cost=total_cost,
        errors=errors,
    )


def make_slug(title: str, max_chars: int = 30) -> str:
    words: list[str] = []
    current = []
    for char in title.lower():
        if char.isascii() and char.isalnum():
            current.append(char)
        elif "\u4e00" <= char <= "\u9fff":
            if current:
                words.append("".join(current))
                current = []
            pinyin = PINYIN_MAP.get(char)
            if pinyin:
                words.append(pinyin)
        else:
            if current:
                words.append("".join(current))
                current = []
    if current:
        words.append("".join(current))
    slug = "-".join(words)
    slug = re.sub(r"-+", "-", slug).strip("-")[:max_chars].strip("-")
    return slug or "book-skill"


def _pick_frameworks(integrated: dict, skeleton) -> list[dict]:
    value = integrated.get("merged_frameworks") or integrated.get("frameworks") or skeleton.frameworks
    return _ensure_dict_list(value)


def _pick_chapter_index(integrated: dict, skeleton) -> list[dict]:
    value = integrated.get("chapter_index") or skeleton.chapter_index
    return _ensure_dict_list(value)


def _pick_glossary(integrated: dict, skeleton) -> list[dict]:
    value = integrated.get("glossary") or skeleton.glossary
    return _ensure_dict_list(value)


def _pick_triggers(integrated: dict) -> list[str]:
    value = integrated.get("triggers") or integrated.get("use_cases") or []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _ensure_dict_list(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            result.append(item)
        else:
            result.append({"name": str(item), "description": ""})
    return result


def _result(
    success: bool,
    start: float,
    zip_path: Path | None = None,
    total_tokens: int = 0,
    total_cost: float = 0.0,
    errors: list[str] | None = None,
) -> PipelineResult:
    return PipelineResult(
        success=success,
        zip_path=str(zip_path) if zip_path else None,
        total_tokens=total_tokens,
        total_cost=round(total_cost, 6),
        elapsed_seconds=round(time.monotonic() - start, 3),
        errors=errors or [],
    )
