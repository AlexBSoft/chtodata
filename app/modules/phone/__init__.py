"""Модуль «телефоны»: очистка и разбор телефонных номеров.

Экспортирует объект :data:`module`, который регистрируется в ``app/modules/__init__.py``
и автоматически подключается ядром (роутер, хуки старта/остановки, health, документация).
"""

from __future__ import annotations

from app.module import Module
from app.modules.phone.registry import registry
from app.modules.phone.router import router
from app.modules.phone.updater import (
    ensure_database,
    start_scheduler,
    status,
    stop_scheduler,
)


def _on_startup() -> None:
    ensure_database()
    start_scheduler()


def _on_shutdown() -> None:
    stop_scheduler()
    registry.close()


def _context() -> dict:
    # Доступно в шаблоне документации как переменная `phone`.
    return status()


module = Module(
    name="phone",
    title="Телефоны",
    description=(
        "Очистка и разбор телефонных номеров из произвольной строки. "
        "Российские номера обогащаются данными реестра Минцифры (оператор, регион, город), "
        "зарубежные — встроенными базами phonenumbers."
    ),
    router=router,
    path="/api/v1/clean/phone",
    doc_template="modules/phone.html",
    on_startup=_on_startup,
    on_shutdown=_on_shutdown,
    health=status,
    context=_context,
)
