import re
import shutil
import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
ChapterMarkdown = tuple[str, str, str, int, int]


def build_skill_package(
    title: str,
    slug: str,
    skill_md_content: str,
    chapter_mds: list[ChapterMarkdown],
    glossary_terms: list[dict] | list[str] | None = None,
    spine_md: str = "",
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
        (work_dir / "chapters").mkdir()
        (work_dir / "raw").mkdir()

        (work_dir / "SKILL.md").write_text(skill_md_content.strip() + "\n", encoding="utf-8")
        (work_dir / "raw" / "spine.md").write_text(spine_md.strip() + "\n", encoding="utf-8")

        env = _get_template_env()
        (work_dir / "README.md").write_text(
            env.get_template("README.md.j2").render(
                title=title,
                slug=slug,
                chapter_count=len(chapter_mds),
                has_glossary=bool(glossary_terms),
            ),
            encoding="utf-8",
        )

        for number, title_text, markdown, _, _ in chapter_mds:
            filename = _safe_filename(f"{number}-{title_text}.md")
            (work_dir / "chapters" / filename).write_text(markdown.strip() + "\n", encoding="utf-8")

        glossary_terms = glossary_terms or _extract_glossary_terms(spine_md)
        if glossary_terms:
            guides_dir = work_dir / "guides"
            guides_dir.mkdir()
            (guides_dir / "glossary.md").write_text(
                _format_glossary_md(glossary_terms),
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


def _format_glossary_md(glossary_terms: list[dict] | list[str]) -> str:
    lines = ["# 术语表", "", "| 术语 | 定义 | 章节 |", "|------|------|------|"]
    for item in glossary_terms:
        if isinstance(item, dict):
            term = item.get("term") or item.get("name") or ""
            definition = item.get("definition") or item.get("description") or ""
            chapter = item.get("chapter") or item.get("chapter_number") or ""
        else:
            term = str(item)
            definition = ""
            chapter = ""
        lines.append(f"| {term} | {definition} | {chapter} |")
    return "\n".join(lines) + "\n"


def _extract_glossary_terms(spine_md: str) -> list[dict]:
    terms = []
    in_table = False
    for line in spine_md.splitlines():
        if "## 关键术语表" in line:
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in {"术语", "------"} or set(cells[0]) == {"-"}:
            continue
        terms.append({"term": cells[0], "definition": cells[1], "chapter": cells[2]})
    return terms


def _zip_directory_contents(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir))


def _safe_filename(filename: str) -> str:
    filename = re.sub(r"[\\/:*?\"<>|]+", "-", filename)
    filename = re.sub(r"\s+", " ", filename).strip()
    return filename or "chapter.md"
