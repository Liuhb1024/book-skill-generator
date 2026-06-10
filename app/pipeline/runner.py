import re
import time
from pathlib import Path

from app.models import PipelineResult
from app.pipeline.stage0_extract import extract
from app.pipeline.stage1_skeleton import extract_distillable_score, run_skeleton_extraction
from app.pipeline.stage2_chapters import run_chapter_distillation
from app.pipeline.stage3_integrate import run_integration
from app.pipeline.stage4_package import build_skill_package


PINYIN_MAP = {
    "刻": "ke",
    "意": "yi",
    "练": "lian",
    "习": "xi",
    "如": "ru",
    "何": "he",
    "从": "cong",
    "新": "xin",
    "手": "shou",
    "到": "dao",
    "大": "da",
    "师": "shi",
    "测": "ce",
    "试": "shi",
    "书": "shu",
    "学": "xue",
    "方": "fang",
    "法": "fa",
    "为": "wei",
    "什": "shen",
    "么": "me",
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
        return _result(False, start, errors=[f"Stage 0 extract failed: {exc}"])

    title = meta.title or filepath.stem.split("_", 1)[-1].strip()
    slug = make_slug(title)

    try:
        spine_md, prompt_tokens, completion_tokens, cost = run_skeleton_extraction(
            chapters,
            full_text,
            book_title=title,
        )
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost
    except Exception as exc:
        return _result(False, start, errors=errors + [f"Stage 1 skeleton failed: {exc}"])

    distillable_score = extract_distillable_score(spine_md)
    if distillable_score < 0.3:
        return _result(
            False,
            start,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            total_cost=total_cost,
            errors=errors + [f"Distillable score too low: {distillable_score}"],
        )

    try:
        chapter_mds, prompt_tokens, completion_tokens, cost = await run_chapter_distillation(chapters)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost
        for number, title_text, markdown, _, _ in chapter_mds:
            if "蒸馏失败" in markdown:
                errors.append(f"Stage 2 chapter {number} failed: {title_text}")
    except Exception as exc:
        return _result(
            False,
            start,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            total_cost=total_cost,
            errors=errors + [f"Stage 2 chapter distillation failed: {exc}"],
        )

    try:
        skill_md_content, prompt_tokens, completion_tokens, cost = run_integration(
            spine_md,
            chapter_mds,
            book_title=title,
            author=meta.author or "未知",
            slug=slug,
        )
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost
    except Exception as exc:
        return _result(
            False,
            start,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            total_cost=total_cost,
            errors=errors + [f"Stage 3 integration failed: {exc}"],
        )

    try:
        zip_path = build_skill_package(
            title=title,
            slug=slug,
            skill_md_content=skill_md_content,
            chapter_mds=chapter_mds,
            glossary_terms=[],
            spine_md=spine_md,
        )
    except Exception as exc:
        return _result(
            False,
            start,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            total_cost=total_cost,
            errors=errors + [f"Stage 4 packaging failed: {exc}"],
        )

    return _result(
        True,
        start,
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
