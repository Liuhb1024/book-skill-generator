import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.models import ChapterInfo


def test_health_check():
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_home_returns_200():
    from app.main import app

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_upload_rejects_unsupported_extension():
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/upload",
        files={"file": ("book.doc", b"hello", "application/msword")},
    )

    assert response.status_code == 400


def test_upload_rejects_file_too_large(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.settings, "MAX_FILE_SIZE_MB", 0)
    client = TestClient(main.app)
    response = client.post(
        "/api/upload",
        files={"file": ("book.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 413


def test_upload_rejects_bad_magic():
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/upload",
        files={"file": ("book.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 400


def test_upload_success(tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.settings, "UPLOAD_DIR", str(tmp_path))
    client = TestClient(main.app)
    response = client.post(
        "/api/upload",
        files={"file": ("sample.txt", "第一章 测试\n内容".encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_id"]
    assert payload["filename"] == "sample.txt"
    assert payload["size"] > 0
    assert list(tmp_path.glob(f"{payload['file_id']}_sample.txt"))


def test_download_404():
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/download/missing.zip")

    assert response.status_code == 404


def test_sse_distill_mock_api(tmp_path, monkeypatch):
    import app.main as main
    from app.models import BookFormat, BookMeta

    upload_path = tmp_path / "abc_sample.txt"
    upload_path.write_text("第一章 测试\n内容\n第二章 继续\n内容", encoding="utf-8")
    zip_path = tmp_path / "sample_skill.zip"
    zip_path.write_bytes(b"zip")

    monkeypatch.setattr(main.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(main.settings, "OUTPUT_DIR", str(tmp_path))

    def fake_extract(filepath):
        return (
            BookMeta(format=BookFormat.TXT, total_chars=20, chapter_count=2),
            [
                ChapterInfo(index=0, number="一", display_number="一", file_number="01", label="ch01", title="测试", content="内容", char_count=2),
                ChapterInfo(index=1, number="二", display_number="二", file_number="02", label="ch02", title="继续", content="内容", char_count=2),
            ],
            "全文",
        )

    def fake_skeleton(chapters, full_text, book_title="sample"):
        return (
            "# 《sample》知识骨架\n\n## 全书核心论点\n核心论点\n\n## 可蒸馏度评估\n- 评分：0.9\n- 理由：可蒸馏",
            10,
            5,
            0.01,
        )

    async def fake_process_one_chapter(chapter, semaphore):
        return (
            chapter.file_number,
            chapter.title,
            f"# 第{chapter.display_number}章：{chapter.title}\n\n## 核心要旨\n内容",
            3,
            2,
        )

    def fake_integrate(spine_md, chapter_mds, book_title="sample", author="未知", slug="sample"):
        return ("---\nname: sample\ndescription: test\nallowed-tools: Read\n---\n\n## 如何使用这个 Skill\n", 4, 2, 0.002)

    def fake_package(**kwargs):
        return zip_path

    monkeypatch.setattr(main, "extract", fake_extract)
    monkeypatch.setattr(main, "run_skeleton_extraction", fake_skeleton)
    monkeypatch.setattr(main, "_process_one_chapter", fake_process_one_chapter)
    monkeypatch.setattr(main, "run_integration", fake_integrate)
    monkeypatch.setattr(main, "build_skill_package", fake_package)

    client = TestClient(main.app)
    response = client.get("/api/distill/abc")

    assert response.status_code == 200
    body = response.text
    assert "event: stage0" in body
    assert "event: stage1" in body
    assert "event: stage2" in body
    assert "event: stage3" in body
    assert "event: stage4" in body
    assert "event: complete" in body
    complete_line = [line for line in body.splitlines() if line.startswith("data:")][-1]
    complete_payload = json.loads(complete_line.removeprefix("data: "))
    assert complete_payload["zip_filename"] == "sample_skill.zip"
    assert complete_payload["download_path"] == "/api/download/sample_skill.zip"


def test_sse_missing_upload_returns_error(tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.settings, "UPLOAD_DIR", str(tmp_path))
    client = TestClient(main.app)
    response = client.get("/api/distill/missing")

    assert response.status_code == 200
    assert "event: error" in response.text
