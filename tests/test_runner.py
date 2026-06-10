import asyncio
import zipfile
from pathlib import Path

import pytest

from app.config import settings
from app.pipeline.runner import run_pipeline


@pytest.mark.skipif(not settings.DEEPSEEK_API_KEY, reason="DEEPSEEK_API_KEY not configured")
def test_run_pipeline_txt(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))

    result = asyncio.run(run_pipeline(Path("test_fixtures/sample.txt")))

    assert result.success is True
    assert result.zip_path is not None
    zip_path = Path(result.zip_path)
    assert zip_path.exists()
    assert result.total_tokens > 0
    assert result.total_cost > 0
    assert result.elapsed_seconds > 0

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())

    assert "SKILL.md" in names
    assert "README.md" in names
    assert any(name.startswith("chapters/") and name.endswith(".md") for name in names)
