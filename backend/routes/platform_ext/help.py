"""
Help & User Guide — serves the in-app user manual.

The manual is stored as Markdown at /app/memory/USER_MANUAL.md and the video
script at /app/memory/VIDEO_SCRIPT.md. Both are loaded once and kept in memory.

Endpoints
---------
GET /api/help/manual        full markdown
GET /api/help/video-script  full markdown
GET /api/help/index         section index for quick links
"""
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from typing import List
import re


MANUAL_PATH = Path("/app/memory/USER_MANUAL.md")
SCRIPT_PATH = Path("/app/memory/VIDEO_SCRIPT.md")


def _load_text(p: Path) -> str:
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def _build_index(md: str) -> List[dict]:
    """Build a flat list of {level, anchor, title} from `## ` and `### ` headings."""
    out = []
    for line in md.splitlines():
        m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        anchor = re.sub(r"[^\w\s-]", "", title.lower()).strip().replace(" ", "-")
        out.append({"level": level, "title": title, "anchor": anchor})
    return out


def create_help_router(require_roles):
    router = APIRouter()

    @router.get("/help/manual")
    async def manual(current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance"))):
        text = _load_text(MANUAL_PATH)
        if not text:
            raise HTTPException(404, "Manual not available on this deployment.")
        return {"format": "markdown", "content": text, "version": "1.0"}

    @router.get("/help/video-script")
    async def video_script(current_user: dict = Depends(require_roles("admin", "manager"))):
        text = _load_text(SCRIPT_PATH)
        if not text:
            raise HTTPException(404, "Video script not available on this deployment.")
        return {"format": "markdown", "content": text, "version": "1.0"}

    @router.get("/help/index")
    async def index(current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance"))):
        text = _load_text(MANUAL_PATH)
        if not text:
            return {"sections": []}
        return {"sections": _build_index(text)}

    return router
