from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.settings import get_settings

settings = get_settings()


def ensure_storage_dirs() -> None:
    for directory in [
        settings.storage_root,
        settings.storage_root / "playbooks",
        settings.storage_root / "packages",
        settings.storage_root / "exports",
    ]:
        directory.mkdir(parents=True, exist_ok=True)


async def persist_upload(upload: UploadFile, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "upload.bin").suffix.lower()
    safe_stem = Path(upload.filename or "upload").stem.replace(" ", "-")[:60] or "upload"
    target = folder / f"{safe_stem}-{uuid4().hex[:8]}{suffix}"
    contents = await upload.read()
    target.write_bytes(contents)
    await upload.seek(0)
    return target
