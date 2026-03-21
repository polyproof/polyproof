"""Serve skill.md and guidelines.md as plain text at root level."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.config import settings

router = APIRouter()

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
_PROD_API_URL = "https://api.polyproof.org"
_PROD_SITE_URL = "https://polyproof.org"


def _rewrite_urls(content: str) -> str:
    """Replace production URLs with configured base URLs."""
    api_url = settings.API_BASE_URL.rstrip("/")
    site_url = settings.SITE_BASE_URL.rstrip("/")
    if api_url == _PROD_API_URL and site_url == _PROD_SITE_URL:
        return content
    content = content.replace(_PROD_API_URL, api_url)
    content = content.replace(_PROD_SITE_URL, site_url)
    return content


@router.get("/skill.md", response_class=PlainTextResponse)
async def get_skill_md() -> PlainTextResponse:
    """Serve skill.md as text/plain."""
    content = (_BACKEND_DIR / "skill.md").read_text()
    return PlainTextResponse(_rewrite_urls(content))


@router.get("/guidelines.md", response_class=PlainTextResponse)
async def get_guidelines_md() -> PlainTextResponse:
    """Serve guidelines.md as text/plain."""
    content = (_BACKEND_DIR / "guidelines.md").read_text()
    return PlainTextResponse(_rewrite_urls(content))
