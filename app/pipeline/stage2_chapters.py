import asyncio
import re

from app.ai_client import call_ai, estimate_cost
from app.config import settings
from app.models import ChapterInfo
from app.parsers.chapter_detector import distillable_chapters
from app.prompts.chapter import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

ChapterMarkdown = tuple[str, str, str, int, int]


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


def _has_repetition_loop(text: str, char_threshold: int = 10) -> bool:
    """检测字符级/2-gram/3-gram 连续重复。

    例如 "夫夫夫夫夫夫夫夫夫夫夫" 会被 (.)\1{10,} 匹配。
    阈值 10 意味着同一字符连续出现 11 次才触发。
    """
    if re.search(r"(.)\1{" + str(char_threshold) + r",}", text):
        return True
    if re.search(r"(.{2})\1{" + str(char_threshold // 2) + r",}", text):
        return True
    if re.search(r"(.{3})\1{" + str(char_threshold // 3) + r",}", text):
        return True
    return False


async def run_chapter_distillation(
    chapters: list[ChapterInfo],
    max_concurrent: int = 10,
) -> tuple[list[ChapterMarkdown], int, int, float]:
    target_chapters = distillable_chapters(chapters)
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [_process_one_chapter(chapter, semaphore) for chapter in target_chapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    outputs: list[ChapterMarkdown] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0

    for chapter, result in zip(target_chapters, results):
        if isinstance(result, Exception):
            outputs.append(_failed_chapter_markdown(chapter, result))
            continue

        number, title, chapter_md, prompt_tokens, completion_tokens = result
        outputs.append((number, title, chapter_md, prompt_tokens, completion_tokens))
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += estimate_cost(prompt_tokens, completion_tokens, model=settings.CHAPTER_MODEL)

    return outputs, total_prompt_tokens, total_completion_tokens, round(total_cost, 6)


async def _process_one_chapter(
    chapter: ChapterInfo,
    semaphore: asyncio.Semaphore,
) -> ChapterMarkdown:
    async with semaphore:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                user_prompt = USER_PROMPT_TEMPLATE.format(
                    chapter_number=chapter.display_number or chapter.number,
                    chapter_title=chapter.title,
                    chapter_content=_trim_chapter_content(chapter.content),
                )
                freq_pen = 0.5 + attempt * 0.3
                pres_pen = 0.3 + attempt * 0.1
                content, prompt_tokens, completion_tokens = await asyncio.to_thread(
                    call_ai,
                    SYSTEM_PROMPT,
                    user_prompt,
                    model=settings.CHAPTER_MODEL,
                    response_format=None,
                    max_tokens=4096,
                    frequency_penalty=freq_pen,
                    presence_penalty=pres_pen,
                )
                if _has_repetition_loop(content):
                    raise RuntimeError(
                        f"检测到字符级重复循环 (attempt {attempt + 1}/3, "
                        f"freq_pen={freq_pen}, pres_pen={pres_pen})，将重试"
                    )
                return (
                    chapter.file_number or chapter.number,
                    chapter.title,
                    _ensure_chapter_heading(_strip_code_fence(content), chapter),
                    prompt_tokens,
                    completion_tokens,
                )
            except Exception as exc:
                last_error = exc
        return _failed_chapter_markdown(chapter, last_error or RuntimeError("unknown chapter failure"))


def _failed_chapter_markdown(chapter: ChapterInfo, exc: Exception) -> ChapterMarkdown:
    number = chapter.file_number or chapter.number
    title = chapter.title
    display = chapter.display_number or chapter.number
    md = (
        f"# 第{display}章：{title}\n\n"
        "## 核心要旨\n"
        f"本章蒸馏失败：{exc}\n\n"
        "## 关键收获\n"
        "1. 需要重新运行本章蒸馏。\n"
    )
    return number, title, md, 0, 0


def _ensure_chapter_heading(markdown: str, chapter: ChapterInfo) -> str:
    if markdown.lstrip().startswith("# "):
        return markdown.strip()
    display = chapter.display_number or chapter.number
    return f"# 第{display}章：{chapter.title}\n\n{markdown.strip()}"


def _strip_code_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()
