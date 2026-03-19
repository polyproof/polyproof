"""Serve skill.md and guidelines.md as plain text at root level."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent


@router.get("/skill.md", response_class=PlainTextResponse)
async def get_skill_md() -> PlainTextResponse:
    """Serve skill.md as text/plain."""
    content = (_BACKEND_DIR / "skill.md").read_text()
    return PlainTextResponse(content)


@router.get("/guidelines.md", response_class=PlainTextResponse)
async def get_guidelines_md() -> PlainTextResponse:
    """Serve guidelines.md as text/plain."""
    content = (_BACKEND_DIR / "guidelines.md").read_text()
    return PlainTextResponse(content)
