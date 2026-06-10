import asyncio
import json
import re
import time
import uuid
import zipfile
from pathlib import Path

import aiofiles
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import AppStatus, EventSourceResponse

from app.ai_client import estimate_cost
from app.config import settings
from app.parsers.base import ParseError
from app.pipeline.runner import make_slug
from app.pipeline.stage0_extract import extract
from app.pipeline.stage1_skeleton import extract_distillable_score, run_skeleton_extraction
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
    destination = upload_dir / f"{file_id}_{_safe_upload_name(filename)}"
    async with aiofiles.open(destination, "wb") as f:
        await f.write(content)

    return {"file_id": file_id, "filename": filename, "size": len(content)}


@app.get("/api/distill/{file_id}")
async def distill(file_id: str, title: str | None = Query(default=None)):
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


@app.get("/api/preview/{zip_filename}/tree")
async def preview_tree(zip_filename: str):
    zip_path = _resolve_preview_zip(zip_filename)
    tree: list[dict] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            _insert_tree_node(tree, info.filename, info.file_size)
    return {"tree": _sort_tree(tree)}


@app.get("/api/preview/{zip_filename}/file")
async def preview_file(zip_filename: str, path: str = Query(...)):
    zip_path = _resolve_preview_zip(zip_filename)
    if ".." in Path(path).parts or path.startswith("/"):
        raise HTTPException(status_code=400, detail="不合法的文件路径")

    with zipfile.ZipFile(zip_path) as zf:
        try:
            info = zf.getinfo(path)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="文件不存在") from exc
        content = zf.read(info).decode("utf-8", errors="replace")

    return {
        "path": path,
        "content": content,
        "type": "markdown" if path.lower().endswith(".md") else "text",
        "size": info.file_size,
    }


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

        book_title = title_override or meta.title or filepath.stem.split("_", 1)[-1].strip()
        slug = make_slug(book_title)
        spine_md, prompt_tokens, completion_tokens, cost = await asyncio.to_thread(
            run_skeleton_extraction,
            chapters,
            full_text,
            book_title,
        )
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost
        score = extract_distillable_score(spine_md)
        yield _event(
            "stage1",
            {
                "distillable_score": score,
                "spine_preview": spine_md[:160],
            },
        )

        if score < 0.3:
            yield _event("error", {"message": f"可蒸馏评分过低: {score}"})
            return

        chapter_mds, p_tokens, c_tokens, stage2_cost = await _distill_chapters_with_progress(chapters)
        total_prompt_tokens += p_tokens
        total_completion_tokens += c_tokens
        total_cost += stage2_cost
        for completed in range(1, len(chapter_mds) + 1):
            yield _event("stage2", {"completed": completed, "total": len(chapter_mds)})

        skill_md_content, prompt_tokens, completion_tokens, cost = await asyncio.to_thread(
            run_integration,
            spine_md,
            chapter_mds,
            book_title,
            meta.author or "未知",
            slug,
        )
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost
        yield _event("stage3", {"message": "SKILL.md 生成完成"})

        zip_path = await asyncio.to_thread(
            build_skill_package,
            title=book_title,
            slug=slug,
            skill_md_content=skill_md_content,
            chapter_mds=chapter_mds,
            glossary_terms=[],
            spine_md=spine_md,
        )
        yield _event("stage4", {"zip_filename": zip_path.name})

        elapsed = round(time.monotonic() - start, 3)
        yield _event(
            "complete",
            {
                "zip_filename": zip_path.name,
                "download_path": f"/api/download/{zip_path.name}",
                "total_tokens": total_prompt_tokens + total_completion_tokens,
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
    target_chapters = [chapter for chapter in chapters if chapter.label.startswith("ch")]
    tasks = [asyncio.create_task(_process_one_chapter(chapter, semaphore)) for chapter in target_chapters]
    outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0

    for task in asyncio.as_completed(tasks):
        number, title, markdown, prompt_tokens, completion_tokens = await task
        outputs.append((number, title, markdown, prompt_tokens, completion_tokens))
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += estimate_cost(prompt_tokens, completion_tokens, model=settings.CHAPTER_MODEL)

    outputs.sort(key=lambda item: item[0])
    return outputs, total_prompt_tokens, total_completion_tokens, round(total_cost, 6)


def _event(event: str, data: dict):
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def _resolve_preview_zip(zip_filename: str) -> Path:
    name = Path(zip_filename).name
    if name != zip_filename or "/" in zip_filename or "\\" in zip_filename or ".." in zip_filename:
        raise HTTPException(status_code=400, detail="不合法的 zip 文件名")
    if not name.endswith("_skill.zip"):
        raise HTTPException(status_code=400, detail="不合法的 zip 文件名")
    path = Path(settings.OUTPUT_DIR) / name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="zip 文件不存在")
    return path


def _insert_tree_node(tree: list[dict], file_path: str, size: int) -> None:
    parts = [part for part in file_path.split("/") if part]
    current = tree
    path_parts = []
    for index, part in enumerate(parts):
        path_parts.append(part)
        node_path = "/".join(path_parts)
        is_file = index == len(parts) - 1
        existing = next((node for node in current if node["name"] == part), None)
        if existing is None:
            existing = {
                "name": part,
                "path": node_path,
                "type": "file" if is_file else "dir",
            }
            if is_file:
                existing["size"] = size
            else:
                existing["children"] = []
            current.append(existing)
        if not is_file:
            current = existing["children"]


def _sort_tree(nodes: list[dict]) -> list[dict]:
    for node in nodes:
        if node["type"] == "dir":
            node["children"] = _sort_tree(node["children"])
    return sorted(nodes, key=lambda item: (item["type"] != "dir", item["name"].lower()))


def _find_upload(file_id: str) -> Path | None:
    matches = sorted(Path(settings.UPLOAD_DIR).glob(f"{file_id}_*"))
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
