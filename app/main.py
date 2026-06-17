"""Точка входа FastAPI-приложения ChtoData.

Ядро не знает о конкретных модулях: оно подключает роутеры и хуки жизненного цикла
всех модулей из ``app.modules.MODULES``. Новый модуль добавляется без правок здесь.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import settings
from app.core import health, web
from app.modules import MODULES

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("chtodata")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(
        "Запуск ChtoData %s (данные: %s, модулей: %d)",
        __version__, settings.data_dir, len(MODULES),
    )
    for module in MODULES:
        if module.on_startup:
            log.info("Инициализация модуля «%s»", module.name)
            module.on_startup()
    log.info("Сервис готов принимать запросы")
    yield
    log.info("Остановка сервиса")
    for module in reversed(MODULES):
        if module.on_shutdown:
            module.on_shutdown()


app = FastAPI(
    title="ChtoData API",
    description="Открытый сервис обработки данных для рунета.",
    version=__version__,
    docs_url="/swagger",  # /docs занят страницей документации на русском
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Общие (ядро) и модульные роутеры.
app.include_router(health.router)
app.include_router(web.router)
for module in MODULES:
    app.include_router(module.router)
