from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.tools._utils import safe_path
from app.tools.list_dir import build_dir_tree

router = APIRouter(prefix="/fs", tags=["fs"])


@router.get("/tree")
async def get_tree(
    path: str = Query(default=".", description="Relative path within workspace"),
    depth: int = Query(default=2, ge=1, le=5),
) -> dict[str, Any]:
    try:
        return build_dir_tree(path, depth, excluded={"code"})
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    dir: str = Query(default=".", description="Target directory relative to workspace"),
) -> dict[str, str]:
    try:
        target_dir = safe_path(dir)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not target_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"'{dir}' is not a directory")
    dest = target_dir / (file.filename or "upload")
    content = await file.read()
    dest.write_bytes(content)
    from app.config import get_workspace_root
    rel = str(dest.relative_to(get_workspace_root()))
    return {"path": rel, "size": len(content)}


@router.get("/download")
async def download_file(
    path: str = Query(description="Relative path to the file within workspace"),
) -> FileResponse:
    try:
        target = safe_path(path)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )
