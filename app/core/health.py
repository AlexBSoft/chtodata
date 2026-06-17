"""Общий эндпоинт состояния сервиса, агрегирующий health всех модулей."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules import MODULES

router = APIRouter(tags=["Служебные"])


@router.get("/api/health", summary="Проверка состояния")
def health() -> dict:
    modules = {m.name: m.health() for m in MODULES if m.health}
    return {"status": "ok", "modules": modules}
