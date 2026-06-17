"""Эндпоинты модуля «телефоны»."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Header, HTTPException

from app.config import settings
from app.modules.phone.models import PhoneResult
from app.modules.phone.parser import parse_phone
from app.modules.phone.updater import update_database

log = logging.getLogger("chtodata.phone")

router = APIRouter(tags=["Телефон"])

_EXAMPLE = ["раб 846)231.60.14 *139", "+7 999 123-45-67"]


@router.post(
    "/api/v1/clean/phone",
    response_model=list[PhoneResult],
    summary="Очистка и разбор телефонов",
)
def clean_phone(sources: list[str] = Body(..., examples=[_EXAMPLE])) -> list[PhoneResult]:
    """Принимает JSON-массив строк с номерами, возвращает массив разобранных объектов.

    Обычный (не async) обработчик — FastAPI выполнит его в пуле потоков, что безопасно
    для синхронных обращений к SQLite.
    """
    return [parse_phone(s) for s in sources]


@router.post(
    "/api/admin/refresh",
    tags=["Служебные"],
    summary="Обновить базу Минцифры",
)
def refresh(
    download: bool = True,
    x_admin_token: str | None = Header(default=None),
) -> dict:
    """Ручной запуск обновления базы. Требует заголовок ``X-Admin-Token``.

    Отключён, если переменная окружения ``CHTODATA_ADMIN_TOKEN`` не задана.
    """
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="Обновление через API отключено")
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Неверный токен")
    stats = update_database(download=download)
    return {"status": "ok", "rows": stats["rows"], "skipped": stats.get("skipped", 0)}
