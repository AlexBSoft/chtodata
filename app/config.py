"""Общая конфигурация приложения (инфраструктура, не привязанная к модулям).

Параметры конкретных модулей (например, источник данных Минцифры для телефонов)
живут внутри самих модулей — см. ``app/modules/<name>/``.

Все параметры переопределяются переменными окружения с префиксом ``CHTODATA_``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Корень проекта (app/config.py -> app -> корень).
BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str) -> str:
    return os.environ.get(f"CHTODATA_{name}", default)


@dataclass(frozen=True)
class Settings:
    # Каталог данных, общий для всех модулей (каждый кладёт свои файлы внутрь).
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", str(BASE_DIR / "data"))))

    # Сетевые параметры HTTP-сервера.
    host: str = field(default_factory=lambda: _env("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(_env("PORT", "8000")))

    # Уровень логирования (DEBUG/INFO/WARNING/ERROR).
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO").upper())

    # Канонический адрес сайта для SEO/OpenGraph (без завершающего слэша).
    site_url: str = field(
        default_factory=lambda: _env("SITE_URL", "https://chtodata.ru").rstrip("/")
    )

    # Автообновление наборов данных (используется модулями с внешними источниками).
    update_enabled: bool = field(
        default_factory=lambda: _env("UPDATE_ENABLED", "true").lower() in ("1", "true", "yes")
    )
    update_interval_days: int = field(
        default_factory=lambda: int(_env("UPDATE_INTERVAL_DAYS", "7"))
    )
    update_hour: int = field(default_factory=lambda: int(_env("UPDATE_HOUR", "4")))

    # Параметры скачивания/сборки наборов данных.
    download_timeout: float = field(
        default_factory=lambda: float(_env("DOWNLOAD_TIMEOUT", "180"))
    )
    download_retries: int = field(
        default_factory=lambda: int(_env("DOWNLOAD_RETRIES", "3"))
    )
    # Защита от «битого» обновления: новый набор не заменит рабочий, если в нём
    # меньше строк, чем это число.
    min_rows: int = field(default_factory=lambda: int(_env("MIN_ROWS", "100000")))

    # Токен для служебных операций (например, ручного обновления данных модуля).
    # Пустой => соответствующие эндпоинты отключены.
    admin_token: str = field(default_factory=lambda: _env("ADMIN_TOKEN", ""))


settings = Settings()
