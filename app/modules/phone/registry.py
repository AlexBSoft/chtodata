"""Реестр Минцифры в SQLite: сборка из CSV и поиск диапазона по номеру.

Схема таблицы ``ranges`` повторяет структуру CSV (код 3 цифры + диапазон 7 цифр),
плюс колонка ``kind`` (ABC/DEF) из имени файла. Поиск — по коду и попаданию номера
в диапазон, при пересечениях побеждает самый узкий диапазон.
"""

from __future__ import annotations

import csv
import os
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.modules.phone import source

# Увеличиваем лимит на размер поля: в 8-800 «Территория ГАР» — очень длинная строка.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

_SCHEMA = """
CREATE TABLE ranges (
    code      INTEGER NOT NULL,
    num_from  INTEGER NOT NULL,
    num_to    INTEGER NOT NULL,
    operator  TEXT,
    region    TEXT,
    territory TEXT,
    inn       TEXT,
    kind      TEXT
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""

_INDEX = "CREATE INDEX idx_lookup ON ranges(code, num_from, num_to);"

_BATCH = 50_000


def build_db(
    csv_dir: Path,
    db_tmp_path: Path,
    file_kinds: dict[str, str] | None = None,
) -> dict[str, int]:
    """Собирает SQLite-базу из CSV-файлов реестра во временный файл ``db_tmp_path``.

    Возвращает статистику: число вставленных и пропущенных строк по файлам и всего.
    Не делает атомарную замену — это ответственность вызывающего кода.
    """
    file_kinds = file_kinds or source.FILES
    db_tmp_path.parent.mkdir(parents=True, exist_ok=True)
    if db_tmp_path.exists():
        db_tmp_path.unlink()

    conn = sqlite3.connect(db_tmp_path)
    stats: dict[str, int] = {"rows": 0, "skipped": 0}
    try:
        conn.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;")
        conn.executescript(_SCHEMA)

        for filename, kind in file_kinds.items():
            path = csv_dir / filename
            if not path.exists():
                raise FileNotFoundError(f"Нет файла реестра: {path}")
            inserted, skipped = _load_csv(conn, path, kind)
            stats[filename] = inserted
            stats["rows"] += inserted
            stats["skipped"] += skipped

        conn.executescript(_INDEX)
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            [
                ("rows", str(stats["rows"])),
                ("updated_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return stats


def _load_csv(conn: sqlite3.Connection, path: Path, kind: str) -> tuple[int, int]:
    """Потоково читает один CSV и пачками вставляет строки. Возвращает (вставлено, пропущено)."""
    inserted = 0
    skipped = 0
    batch: list[tuple] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader, None)  # заголовок
        for row in reader:
            if len(row) < 8:
                skipped += 1
                continue
            try:
                code = int(row[0])
                num_from = int(row[1])
                num_to = int(row[2])
            except (ValueError, IndexError):
                skipped += 1
                continue
            batch.append(
                (
                    code,
                    num_from,
                    num_to,
                    row[4].strip(),
                    row[5].strip(),
                    row[6].strip(),
                    row[7].strip(),
                    kind,
                )
            )
            if len(batch) >= _BATCH:
                conn.executemany(
                    "INSERT INTO ranges VALUES (?,?,?,?,?,?,?,?)", batch
                )
                inserted += len(batch)
                batch.clear()
    if batch:
        conn.executemany("INSERT INTO ranges VALUES (?,?,?,?,?,?,?,?)", batch)
        inserted += len(batch)
    return inserted, skipped


def swap_db(db_tmp_path: Path, db_path: Path) -> None:
    """Атомарно заменяет рабочую базу собранной временной. На Windows требует,
    чтобы рабочая база не была открыта — поэтому вызывается под блокировкой реестра."""
    os.replace(db_tmp_path, db_path)


class Registry:
    """Потокобезопасная обёртка над одним SQLite-соединением (только чтение).

    Все обращения сериализуются блокировкой — это упрощает безопасную «горячую»
    замену файла базы при обновлении (важно на Windows, где нельзя заменить открытый файл).
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    @property
    def available(self) -> bool:
        return self._conn is not None

    def open(self) -> None:
        with self._lock:
            self._open_locked()

    def _open_locked(self) -> None:
        if self._conn is not None:
            return
        if not self._db_path.exists():
            return
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def reload(self) -> None:
        """Переоткрывает соединение (после замены файла базы)."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
            self._open_locked()

    def replace_with(self, db_tmp_path: Path) -> None:
        """Атомарно заменяет файл базы на собранный и переоткрывает соединение.

        Закрытие, замена и переоткрытие выполняются под одной блокировкой, чтобы
        параллельные запросы не держали открытым старый файл во время os.replace
        (на Windows замену открытого файла выполнить нельзя)."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
            os.replace(db_tmp_path, self._db_path)
            self._open_locked()

    def lookup(self, code: int, number: int) -> dict | None:
        """Ищет запись для кода ABC/DEF и 7-значного номера. Узкий диапазон побеждает."""
        with self._lock:
            if self._conn is None:
                self._open_locked()
            if self._conn is None:
                return None
            cur = self._conn.execute(
                "SELECT operator, region, territory, inn, kind FROM ranges "
                "WHERE code=? AND num_from<=? AND num_to>=? "
                "ORDER BY (num_to - num_from) ASC LIMIT 1",
                (code, number, number),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def meta(self, key: str) -> str | None:
        with self._lock:
            if self._conn is None:
                self._open_locked()
            if self._conn is None:
                return None
            cur = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,))
            row = cur.fetchone()
            return row["value"] if row else None


# Глобальный экземпляр, используемый приложением.
registry = Registry(source.DB_PATH)
