#!/usr/bin/env python
"""CLI для сборки/обновления базы реестра Минцифры.

Примеры:
    python scripts/build_db.py              # собрать из локальных CSV (data/mincifry-phones)
    python scripts/build_db.py --download   # скачать свежие CSV и собрать
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Позволяет запускать скрипт напрямую: добавляем корень проекта в sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.phone import source  # noqa: E402
from app.modules.phone.updater import update_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Сборка базы реестра Минцифры (SQLite)")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Скачать свежие CSV с opendata.digital.gov.ru перед сборкой",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    origin = "скачанных" if args.download else f"локальных CSV ({source.CSV_DIR})"
    print(f"Сборка базы из {origin} ...")
    stats = update_database(download=args.download)
    print(f"Готово: {stats['rows']} строк, пропущено {stats.get('skipped', 0)}.")
    print(f"База: {source.DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
