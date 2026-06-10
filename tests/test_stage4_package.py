import zipfile

from app.models import ChapterOutput
from app.pipeline.stage4_package import build_skill_package


def test_build_skill_package(tmp_path):
    zip_path = build_skill_package(
        title="测试书",
        slug="test-book",
        thesis="这是本书核心。",
        frameworks=[
            {"name": "费曼技巧", "description": "用自己的话解释概念", "related_chapters": ["二"]},
        ],
        chapter_index=[
            {"chapter_number": "一", "title": "为什么学习", "summary": "学习的本质。"},
        ],
        glossary=[
            {"term": "元认知", "definition": "理解和控制自己的思维过程", "chapter": "一"},
        ],
        triggers=["需要设计学习计划时"],
        chapter_outputs=[
            ChapterOutput(
                chapter_number="一",
                chapter_title="为什么学习",
                frameworks=["元认知循环"],
                methodologies=["间隔重复"],
                cases=["学习方法案例"],
                anti_patterns=["只集中突击"],
                actionable_steps=["安排复盘"],
            )
        ],
        output_dir=tmp_path,
    )

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())

    assert "SKILL.md" in names
    assert "README.md" in names
    assert any(name.startswith("chapters/") and name.endswith(".md") for name in names)
    assert "guides/glossary.md" in names


def test_missing_optional_content(tmp_path):
    zip_path = build_skill_package(
        title="测试书",
        slug="test-book-no-glossary",
        thesis="这是本书核心。",
        frameworks=[],
        chapter_index=[],
        glossary=[],
        triggers=[],
        chapter_outputs=[
            ChapterOutput(
                chapter_number="一",
                chapter_title="为什么学习",
                frameworks=["元认知循环"],
            )
        ],
        output_dir=tmp_path,
    )

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())

    assert "SKILL.md" in names
    assert "README.md" in names
    assert "guides/glossary.md" not in names
