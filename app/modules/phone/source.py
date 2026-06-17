"""Источник данных и пути модуля «телефоны» (реестр Минцифры)."""

from __future__ import annotations

import os
from pathlib import Path

from app.config import settings

# Прямые ссылки на CSV реестра Минцифры (план и система нумерации).
# Хвост ?<timestamp> на сайте — антикэш и необязателен.
DATA_SOURCE_BASE_URL = "https://opendata.digital.gov.ru/downloads"
FILES: dict[str, str] = {
    # имя файла -> вид (ABC = стационарные/географические, DEF = мобильные)
    "ABC-3xx.csv": "ABC",
    "ABC-4xx.csv": "ABC",
    "ABC-8xx.csv": "ABC",
    "DEF-9xx.csv": "DEF",
}

# Файлы данных модуля внутри общего каталога данных.
DB_PATH = settings.data_dir / "registry.db"
DB_TMP_PATH = settings.data_dir / "registry.db.tmp"
DOWNLOAD_DIR = settings.data_dir / "_download"
CSV_DIR = Path(
    os.environ.get("CHTODATA_CSV_DIR", str(settings.data_dir / "mincifry-phones"))
)
