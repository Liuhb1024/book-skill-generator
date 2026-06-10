import re
from datetime import date

from app.ai_client import call_ai, estimate_cost
from app.config import settings
from app.prompts.integrate import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


def run_integration(
    spine_md: str,
    chapter_mds: list[tuple[str, str, str, int, int]],
    book_title: str = "未知书名",
    author: str = "未知",
    slug: str = "book-skill",
) -> tuple[str, int, int, float]:
    chapters_md = "\n\n---\n\n".join(
        f"文件编号：{number}\n章节标题：{title}\n\n{markdown}"
        for number, title, markdown, _, _ in chapter_mds
    )
    user_prompt = USER_PROMPT_TEMPLATE.format(
        book_title=book_title,
        author=author or "未知",
        slug=slug,
        chapter_count=len(chapter_mds),
        generated_date=date.today().isoformat(),
        spine_md=spine_md,
        chapters_md=chapters_md,
    )
    content, prompt_tokens, completion_tokens = call_ai(
        SYSTEM_PROMPT,
        user_prompt,
        model=settings.INTEGRATE_MODEL,
        temperature=0.3,
        response_format=None,
        max_tokens=8192,
    )
    skill_md = _normalize_skill_md(_strip_code_fence(content), slug, book_title, len(chapter_mds))
    cost = estimate_cost(prompt_tokens, completion_tokens, model=settings.INTEGRATE_MODEL)
    return skill_md, prompt_tokens, completion_tokens, cost


def _normalize_skill_md(skill_md: str, slug: str, book_title: str, chapter_count: int) -> str:
    text = skill_md.strip()
    if not text.startswith("---"):
        text = (
            "---\n"
            f"name: {slug}\n"
            f"description: 基于《{book_title}》蒸馏的 AI 技能。当需要运用本书核心框架和方法论时使用。\n"
            "allowed-tools: Read\n"
            "---\n\n"
            f"# 《{book_title}》\n\n"
            f"{text}"
        )
    text = re.sub(r"name:\s*.*", f"name: {slug}", text, count=1)
    if "allowed-tools:" not in text.split("---", 2)[1]:
        text = text.replace("---", "---\nallowed-tools: Read", 1)
    text = re.sub(r"\*\*章节\*\*：\d+章", f"**章节**：{chapter_count}章", text)
    text = re.sub(r"\*\*生成日期\*\*：\d{4}[-:/]\d{1,2}[-:/]\d{1,2}", f"**生成日期**：{date.today().isoformat()}", text)
    return text


def _strip_code_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()
