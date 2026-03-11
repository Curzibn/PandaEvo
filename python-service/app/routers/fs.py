from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.config import get_web_fs_root
from app.tools.list_dir import _build_tree

router = APIRouter(prefix="/fs", tags=["fs"])


def _web_safe_path(rel: str) -> Path:
    web_root = get_web_fs_root()
    target = (web_root / rel).resolve()
    if not str(target).startswith(str(web_root)):
        raise PermissionError(f"Access denied: '{rel}' is outside web workspace root.")
    return target


@router.get("/tree")
async def get_tree(
    path: str = Query(default=".", description="Relative path within web workspace"),
    depth: int = Query(default=2, ge=1, le=5),
) -> dict[str, Any]:
    try:
        target = _web_safe_path(path)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return _build_tree(target, get_web_fs_root(), depth, include_hidden=False)


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    dir: str = Query(default=".", description="Target directory relative to web workspace"),
) -> dict[str, str]:
    try:
        target_dir = _web_safe_path(dir)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not target_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"'{dir}' is not a directory")
    dest = target_dir / (file.filename or "upload")
    content = await file.read()
    dest.write_bytes(content)
    rel = str(dest.relative_to(get_web_fs_root()))
    return {"path": rel, "size": len(content)}


@router.get("/download")
async def download_file(
    path: str = Query(description="Relative path to the file within web workspace"),
) -> FileResponse:
    try:
        target = _web_safe_path(path)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )
