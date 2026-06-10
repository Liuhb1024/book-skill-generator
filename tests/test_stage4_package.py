import zipfile

from app.pipeline.stage4_package import build_skill_package


def test_build_skill_package(tmp_path):
    zip_path = build_skill_package(
        title="测试书",
        slug="test-book",
        skill_md_content="---\nname: test-book\ndescription: test\nallowed-tools: Read\n---\n\n# 测试书\n",
        chapter_mds=[
            ("01", "为什么学习", "# 第一章：为什么学习\n\n## 核心要旨\n学习的本质。", 10, 5),
        ],
        glossary_terms=[
            {"term": "元认知", "definition": "理解和控制自己的思维过程", "chapter": "一"},
        ],
        spine_md="# 骨架",
        output_dir=tmp_path,
    )

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())

    assert "SKILL.md" in names
    assert "README.md" in names
    assert "raw/spine.md" in names
    assert any(name.startswith("chapters/") and name.endswith(".md") for name in names)
    assert "guides/glossary.md" in names


def test_missing_optional_content(tmp_path):
    zip_path = build_skill_package(
        title="测试书",
        slug="test-book-no-glossary",
        skill_md_content="---\nname: test-book-no-glossary\ndescription: test\nallowed-tools: Read\n---\n\n# 测试书\n",
        chapter_mds=[
            ("01", "为什么学习", "# 第一章：为什么学习\n\n## 核心要旨\n学习的本质。", 10, 5),
        ],
        glossary_terms=[],
        spine_md="# 骨架",
        output_dir=tmp_path,
    )

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())

    assert "SKILL.md" in names
    assert "README.md" in names
    assert "raw/spine.md" in names
    assert "guides/glossary.md" not in names
