import re
import shutil
import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.models import ChapterOutput


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def build_skill_package(
    title: str,
    slug: str,
    thesis: str,
    frameworks: list[dict],
    chapter_index: list[dict],
    glossary: list[dict],
    triggers: list[str],
    chapter_outputs: list[ChapterOutput],
    output_dir: Path | str | None = None,
) -> Path:
    base_dir = Path(output_dir or settings.OUTPUT_DIR)
    base_dir.mkdir(parents=True, exist_ok=True)
    work_dir = base_dir / f"{slug}_skill"
    zip_path = base_dir / f"{slug}_skill.zip"

    if work_dir.exists():
        shutil.rmtree(work_dir)
    if zip_path.exists():
        zip_path.unlink()

    try:
        work_dir.mkdir(parents=True)
        chapters_dir = work_dir / "chapters"
        chapters_dir.mkdir()

        env = _get_template_env()
        context = {
            "title": title,
            "slug": slug,
            "thesis": thesis,
            "frameworks": _normalize_frameworks(frameworks),
            "chapter_index": _normalize_chapter_index(chapter_index),
            "glossary": _normalize_glossary(glossary),
            "triggers": triggers,
            "chapter_outputs": chapter_outputs,
        }

        (work_dir / "SKILL.md").write_text(
            env.get_template("SKILL.md.j2").render(**context),
            encoding="utf-8",
        )
        (work_dir / "README.md").write_text(
            env.get_template("README.md.j2").render(**context),
            encoding="utf-8",
        )

        for chapter in chapter_outputs:
            filename = _safe_filename(f"{chapter.chapter_number}-{chapter.chapter_title}.md")
            (chapters_dir / filename).write_text(_format_chapter_md(chapter), encoding="utf-8")

        normalized_glossary = context["glossary"]
        if normalized_glossary:
            guides_dir = work_dir / "guides"
            guides_dir.mkdir()
            (guides_dir / "glossary.md").write_text(
                _format_glossary_md(normalized_glossary),
                encoding="utf-8",
            )

        _zip_directory_contents(work_dir, zip_path)
    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir)

    return zip_path


def _get_template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(disabled_extensions=("j2", "md")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _format_chapter_md(chapter: ChapterOutput) -> str:
    sections = [
        ("核心框架", chapter.frameworks),
        ("方法论/技巧", chapter.methodologies),
        ("书中案例", chapter.cases),
        ("反模式/常见误区", chapter.anti_patterns),
        ("可执行步骤", chapter.actionable_steps),
    ]
    lines = [f"# {chapter.chapter_number} {chapter.chapter_title}", ""]
    for heading, items in sections:
        if not items:
            continue
        lines.extend([f"## {heading}", ""])
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_glossary_md(glossary: list[dict]) -> str:
    lines = ["# 术语速查", "", "| 术语 | 定义 | 章节 |", "|------|------|------|"]
    for item in glossary:
        lines.append(f"| {item['term']} | {item['definition']} | {item['chapter']} |")
    return "\n".join(lines) + "\n"


def _zip_directory_contents(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir))


def _safe_filename(filename: str) -> str:
    filename = re.sub(r"[\\/:*?\"<>|]+", "-", filename)
    filename = re.sub(r"\s+", " ", filename).strip()
    return filename or "chapter.md"


def _normalize_frameworks(frameworks: list[dict]) -> list[dict]:
    normalized = []
    for item in frameworks:
        if not isinstance(item, dict):
            item = {"name": str(item)}
        normalized.append(
            {
                "name": item.get("name") or item.get("title") or "",
                "description": item.get("description") or item.get("summary") or "",
                "related_chapters": item.get("related_chapters") or item.get("chapters") or [],
            }
        )
    return normalized


def _normalize_chapter_index(chapter_index: list[dict]) -> list[dict]:
    normalized = []
    for item in chapter_index:
        normalized.append(
            {
                "chapter_number": item.get("chapter_number") or item.get("number") or item.get("chapter") or "",
                "title": item.get("title") or item.get("topic") or "",
                "summary": item.get("summary") or item.get("description") or "",
            }
        )
    return normalized


def _normalize_glossary(glossary: list[dict]) -> list[dict]:
    normalized = []
    for item in glossary:
        normalized.append(
            {
                "term": item.get("term") or item.get("name") or "",
                "definition": item.get("definition") or item.get("description") or "",
                "chapter": item.get("chapter") or item.get("chapter_number") or "",
            }
        )
    return normalized
