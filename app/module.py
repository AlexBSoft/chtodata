"""Контракт модуля обработки данных.

Каждый модуль (телефоны, а в будущем — почта, адреса, ИНН и т.п.) описывается одним
объектом :class:`Module`: метаданные для страницы документации, свой роутер FastAPI и
опциональные хуки жизненного цикла/здоровья. Добавить новый модуль — значит создать
пакет ``app/modules/<name>/`` с объектом ``module`` и зарегистрировать его в
``app/modules/__init__.py``. Никаких правок в ядре при этом не требуется.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter


@dataclass(frozen=True)
class Module:
    name: str
    """Машинное имя, напр. ``"phone"`` (ключ в /api/health и контексте шаблона)."""

    title: str
    """Человекочитаемое название для страницы документации."""

    description: str
    """Краткое описание модуля для списка модулей."""

    router: APIRouter
    """Роутер FastAPI с эндпоинтами модуля."""

    path: str = ""
    """Основной путь модуля для отображения, напр. ``"/api/v1/clean/phone"``."""

    doc_template: str | None = None
    """Имя Jinja-шаблона с подробной документацией модуля (подключается на странице)."""

    on_startup: Callable[[], None] | None = None
    """Хук старта: подготовка данных, запуск планировщиков и т.п."""

    on_shutdown: Callable[[], None] | None = None
    """Хук остановки: освобождение ресурсов."""

    health: Callable[[], dict] | None = None
    """Возвращает словарь состояния модуля для /api/health."""

    context: Callable[[], dict] | None = None
    """Доп. контекст для страницы документации (доступен в шаблоне как ``<name>``)."""
