import re

from app.ai_client import call_ai, estimate_cost
from app.config import settings
from app.models import ChapterInfo
from app.parsers.chapter_detector import distillable_chapters
from app.prompts.skeleton import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


def build_toc(chapters: list[ChapterInfo]) -> str:
    lines = []
    for chapter in chapters:
        if chapter.label in {"fm", "bm"}:
            continue
        number = chapter.display_number or chapter.number
        lines.append(f"[{number}] {chapter.title}")
    return "\n".join(lines)


def build_preface(full_text: str, max_chars: int = 2000) -> str:
    return full_text[:max_chars]


def build_chapter_glimpses(
    chapters: list[ChapterInfo],
    head_chars: int = 1000,
    tail_chars: int = 1000,
) -> str:
    glimpses = []
    for chapter in distillable_chapters(chapters):
        head = chapter.content[:head_chars]
        tail = chapter.content[-tail_chars:] if tail_chars > 0 else ""
        number = chapter.display_number or chapter.number
        glimpses.append(
            f"[{number}] {chapter.title}\n"
            f"首部:\n{head}\n"
            f"尾部:\n{tail}"
        )
    return "\n\n".join(glimpses)


def run_skeleton_extraction(
    chapters: list[ChapterInfo],
    full_text: str,
    book_title: str = "未知书名",
) -> tuple[str, int, int, float]:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        book_title=book_title,
        toc=build_toc(chapters),
        preface=build_preface(full_text),
        chapter_glimpses=build_chapter_glimpses(chapters),
    )
    content, prompt_tokens, completion_tokens = call_ai(
        SYSTEM_PROMPT,
        user_prompt,
        model=settings.SKELETON_MODEL,
        response_format=None,
        max_tokens=4096,
        frequency_penalty=0.3,
        presence_penalty=0.3,
    )
    spine_md = _strip_code_fence(content)
    cost = estimate_cost(prompt_tokens, completion_tokens, model=settings.SKELETON_MODEL)
    return spine_md, prompt_tokens, completion_tokens, cost


def extract_distillable_score(spine_md: str) -> float:
    patterns = [
        r"评分[：:]\s*([01](?:\.\d+)?)",
        r"distillable[_ -]?score[：:=\s]+([01](?:\.\d+)?)",
        r"可蒸馏度[^0-9]{0,20}([01](?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, spine_md, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return 1.0


def _strip_code_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()
