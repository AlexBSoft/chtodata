"""Веб-страница документации (на русском). Собирается из метаданных модулей."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import __version__
from app.config import settings
from app.modules import MODULES

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


def _context(request: Request) -> dict:
    ctx: dict = {
        "request": request,
        "version": __version__,
        "modules": MODULES,
        "site_url": settings.site_url,
    }
    # Доп. контекст каждого модуля доступен в шаблоне под именем модуля (напр. `phone`).
    for m in MODULES:
        if m.context:
            ctx[m.name] = m.context()
    return ctx


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/docs", response_class=HTMLResponse, include_in_schema=False)
def docs(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("docs.html", _context(request))
