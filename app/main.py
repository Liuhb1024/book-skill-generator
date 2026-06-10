import asyncio
import json
import re
import shutil
import time
import uuid
from pathlib import Path

import aiofiles
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import AppStatus, EventSourceResponse

from app.config import settings
from app.models import ChapterOutput
from app.parsers.base import ParseError
from app.pipeline.runner import (
    _pick_chapter_index,
    _pick_frameworks,
    _pick_glossary,
    _pick_triggers,
    make_slug,
)
from app.pipeline.stage0_extract import extract
from app.pipeline.stage1_skeleton import run_skeleton_extraction
from app.pipeline.stage2_chapters import _process_one_chapter
from app.pipeline.stage3_integrate import run_integration
from app.pipeline.stage4_package import build_skill_package


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
ALLOWED_EXTENSIONS = {".pdf", ".epub", ".txt", ".md"}

app = FastAPI(title="Book Skill Generator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<!doctype html><title>Book Skill Generator</title><h1>Book Skill Generator</h1>")
    return FileResponse(index_path)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    content = await file.read()
    max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail="文件超过大小限制")
    if not _valid_magic(content, suffix):
        raise HTTPException(status_code=400, detail="文件内容与格式不匹配")

    file_id = uuid.uuid4().hex
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_upload_name(filename)
    destination = upload_dir / f"{file_id}_{safe_name}"
    async with aiofiles.open(destination, "wb") as f:
        await f.write(content)

    return {"file_id": file_id, "filename": filename, "size": len(content)}


@app.get("/api/distill/{file_id}")
async def distill(
    file_id: str,
    title: str | None = Query(default=None),
):
    AppStatus.should_exit_event = None
    return EventSourceResponse(_distill_events(file_id, title))


@app.get("/api/download/{file_path:path}")
async def download(file_path: str):
    path = Path(file_path)
    if not path.is_absolute():
        path = Path(settings.OUTPUT_DIR) / path
    if not path.exists() or not path.is_file() or path.suffix != ".zip":
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=path.name, media_type="application/zip")


async def _distill_events(file_id: str, title_override: str | None = None):
    start = time.monotonic()
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0

    try:
        filepath = _find_upload(file_id)
        if filepath is None:
            yield _event("error", {"message": "上传文件不存在"})
            return

        meta, chapters, full_text = await asyncio.to_thread(extract, filepath)
        yield _event("stage0", {"chars": meta.total_chars, "chapters": len(chapters)})

        skeleton, prompt_tokens, completion_tokens, cost = await asyncio.to_thread(
            run_skeleton_extraction,
            chapters,
            full_text,
        )
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost
        yield _event(
            "stage1",
            {
                "frameworks_count": len(skeleton.frameworks),
                "thesis_preview": skeleton.thesis[:120],
            },
        )

        if skeleton.distillable_score < 0.3:
            yield _event("error", {"message": f"可蒸馏评分过低: {skeleton.distillable_score}"})
            return

        chapter_outputs, p_tokens, c_tokens, stage2_cost = await _distill_chapters_with_progress(chapters)
        total_prompt_tokens += p_tokens
        total_completion_tokens += c_tokens
        total_cost += stage2_cost
        for completed in range(1, len(chapters) + 1):
            yield _event("stage2", {"completed": completed, "total": len(chapters)})

        integrated, prompt_tokens, completion_tokens, cost = await asyncio.to_thread(
            run_integration,
            skeleton,
            chapter_outputs,
        )
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost
        yield _event("stage3", {"message": "知识整合完成"})

        book_title = title_override or meta.title or filepath.stem.split("_", 1)[-1]
        slug = make_slug(book_title)
        zip_path = await asyncio.to_thread(
            build_skill_package,
            title=book_title,
            slug=slug,
            thesis=integrated.get("thesis") or skeleton.thesis,
            frameworks=_pick_frameworks(integrated, skeleton),
            chapter_index=_pick_chapter_index(integrated, skeleton),
            glossary=_pick_glossary(integrated, skeleton),
            triggers=_pick_triggers(integrated),
            chapter_outputs=chapter_outputs,
        )
        yield _event("stage4", {"zip_filename": zip_path.name})

        elapsed = round(time.monotonic() - start, 3)
        total_tokens = total_prompt_tokens + total_completion_tokens
        yield _event(
            "complete",
            {
                "zip_filename": zip_path.name,
                "download_path": f"/api/download/{zip_path.name}",
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 6),
                "elapsed_seconds": elapsed,
            },
        )
    except ParseError as exc:
        yield _event("error", {"message": exc.message, "recoverable": exc.recoverable})
    except Exception as exc:
        yield _event("error", {"message": str(exc)})


async def _distill_chapters_with_progress(chapters):
    semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_CHAPTERS)
    tasks = [asyncio.create_task(_process_one_chapter(chapter, semaphore)) for chapter in chapters]
    outputs: list[ChapterOutput] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0

    for task in asyncio.as_completed(tasks):
        result = await task
        output, prompt_tokens, completion_tokens, cost = result
        outputs.append(output)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost

    outputs.sort(key=lambda item: _chapter_sort_key(chapters, item))
    return outputs, total_prompt_tokens, total_completion_tokens, round(total_cost, 6)


def _chapter_sort_key(chapters, output: ChapterOutput) -> int:
    for index, chapter in enumerate(chapters):
        if chapter.number == output.chapter_number:
            return index
    return len(chapters)


def _event(event: str, data: dict):
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def _find_upload(file_id: str) -> Path | None:
    upload_dir = Path(settings.UPLOAD_DIR)
    matches = sorted(upload_dir.glob(f"{file_id}_*"))
    return matches[0] if matches else None


def _valid_magic(content: bytes, suffix: str) -> bool:
    if not content:
        return False
    if suffix == ".pdf":
        return content.startswith(b"%PDF")
    if suffix == ".epub":
        return content.startswith(b"PK") and b"mimetypeapplication/epub+zip" in content[:128].replace(b"\n", b"")
    if suffix in {".txt", ".md"}:
        if b"\x00" in content[:1024]:
            return False
        for encoding in ("utf-8", "gbk", "latin-1"):
            try:
                content.decode(encoding)
                return True
            except UnicodeDecodeError:
                continue
    return False


def _safe_upload_name(filename: str) -> str:
    filename = re.sub(r"[\\/:*?\"<>|]+", "-", filename)
    filename = re.sub(r"\s+", " ", filename).strip()
    return filename or "upload.bin"
