"""Скачивание реестра Минцифры и пересборка SQLite-базы + планировщик обновлений.

Рассчитано на длительную автономную работу (VPS, «поставил и забыл»):
  * скачивание с повторными попытками при сетевых сбоях;
  * сборка во временный файл и проверка вменяемости перед атомарной заменой —
    «битое» обновление никогда не заменит рабочую базу;
  * любые сбои обновления логируются, но не роняют сервис: он продолжает отвечать
    на последней успешной базе;
  * при старте проверяется свежесть базы; устаревшая — обновляется в фоне.
"""

from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.modules.phone import source
from app.modules.phone.registry import build_db, registry

log = logging.getLogger("chtodata.phone.updater")

_scheduler: BackgroundScheduler | None = None


def download_all(dest_dir: Path) -> None:
    """Скачивает все CSV реестра в ``dest_dir`` с повторными попытками."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=settings.download_timeout, follow_redirects=True) as client:
        for filename in source.FILES:
            url = f"{source.DATA_SOURCE_BASE_URL}/{filename}"
            _download_one(client, url, dest_dir / filename)


def _download_one(client: httpx.Client, url: str, dest: Path) -> None:
    attempts = max(1, settings.download_retries)
    last_err: Exception | None = None
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            size = 0
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=1 << 16):
                        fh.write(chunk)
                        size += len(chunk)
            if size == 0:
                raise RuntimeError("пустой файл")
            tmp.replace(dest)
            log.info(
                "Скачан %s: %.1f МБ за %.1f с (попытка %d/%d)",
                dest.name, size / 1e6, time.monotonic() - started, attempt, attempts,
            )
            return
        except Exception as err:  # noqa: BLE001
            last_err = err
            tmp.unlink(missing_ok=True)
            log.warning(
                "Сбой скачивания %s (попытка %d/%d): %s", url, attempt, attempts, err
            )
            if attempt < attempts:
                time.sleep(min(30, 5 * attempt))  # линейный бэкофф
    raise RuntimeError(f"Не удалось скачать {url}: {last_err}")


def rebuild(csv_dir: Path) -> dict[str, int]:
    """Собирает базу из CSV в ``csv_dir`` и атомарно подменяет рабочую базу.

    Перед заменой проверяет, что новая база не «битая»: число строк не меньше порога
    ``MIN_ROWS`` и не упало более чем вдвое относительно текущей базы.
    """
    started = time.monotonic()
    stats = build_db(csv_dir, source.DB_TMP_PATH, source.FILES)
    new_rows = stats["rows"]

    current_rows = int(registry.meta("rows") or 0)
    reason = _reject_reason(new_rows, current_rows)
    if reason:
        source.DB_TMP_PATH.unlink(missing_ok=True)
        raise RuntimeError(f"Обновление отклонено ({reason}); рабочая база сохранена")

    registry.replace_with(source.DB_TMP_PATH)
    log.info(
        "База обновлена: %d строк (было %d, пропущено %d) за %.1f с",
        new_rows, current_rows, stats.get("skipped", 0), time.monotonic() - started,
    )
    return stats


def _reject_reason(new_rows: int, current_rows: int) -> str | None:
    if new_rows < settings.min_rows:
        return f"строк {new_rows} < порога {settings.min_rows}"
    if current_rows > 0 and new_rows < current_rows // 2:
        return f"строк {new_rows} < половины текущих {current_rows}"
    return None


def update_database(download: bool = True) -> dict[str, int]:
    """Полный цикл обновления: (опц.) скачать CSV, собрать базу, подменить."""
    if download:
        dl = source.DOWNLOAD_DIR
        log.info("Запуск обновления базы (скачивание с %s)", source.DATA_SOURCE_BASE_URL)
        download_all(dl)
        try:
            return rebuild(dl)
        finally:
            shutil.rmtree(dl, ignore_errors=True)
    log.info("Запуск сборки базы из локальных CSV (%s)", source.CSV_DIR)
    return rebuild(source.CSV_DIR)


def ensure_database() -> None:
    """Гарантирует наличие базы при старте: если её нет — собирает из локальных CSV,
    при их отсутствии — скачивает и собирает.

    Если первичная сборка не удалась (например, нет сети в контейнере), приложение
    всё равно стартует в усечённом режиме: телефоны разбираются через phonenumbers,
    но без обогащения оператором/регионом. База подтянется при следующем обновлении.
    """
    if source.DB_PATH.exists():
        registry.open()
        log.info(
            "База найдена: %s (строк: %s, обновлена: %s)",
            source.DB_PATH,
            registry.meta("rows"),
            registry.meta("updated_at") or "неизвестно",
        )
        return
    log.info("База не найдена — выполняется первичная сборка")
    try:
        if source.CSV_DIR.exists() and any(source.CSV_DIR.glob("*.csv")):
            update_database(download=False)
        else:
            update_database(download=True)
    except Exception:  # noqa: BLE001
        log.exception("Первичная сборка базы не удалась — старт в режиме без реестра")


def _is_stale() -> bool:
    """True, если база отсутствует или старше интервала обновления."""
    if not registry.available:
        return True
    raw = registry.meta("updated_at")
    if not raw:
        return True
    try:
        updated = datetime.fromisoformat(raw)
    except ValueError:
        return True
    age = datetime.now(timezone.utc) - updated
    return age > timedelta(days=settings.update_interval_days)


def start_scheduler() -> None:
    """Запускает фоновый планировщик периодического обновления базы.

    Дополнительно: если база устарела (например, VPS долго был выключен или часто
    перезапускается, сбрасывая таймер), сразу ставит разовое фоновое обновление.
    """
    global _scheduler
    if not settings.update_enabled:
        log.info("Автообновление отключено (CHTODATA_UPDATE_ENABLED=false)")
        return
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _scheduled_update,
        trigger=IntervalTrigger(days=settings.update_interval_days),
        id="mincifry_update",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    job = _scheduler.get_job("mincifry_update")
    log.info(
        "Планировщик запущен: обновление каждые %d дн., следующий запуск ~%s",
        settings.update_interval_days,
        getattr(job, "next_run_time", "?"),
    )

    if _is_stale():
        log.info("База устарела или отсутствует — запланировано фоновое обновление")
        _scheduler.add_job(_scheduled_update, id="mincifry_update_now", misfire_grace_time=3600)


def _scheduled_update() -> None:
    try:
        update_database(download=True)
    except Exception:  # noqa: BLE001 — не роняем планировщик из-за сетевых сбоев
        log.exception("Плановое обновление базы не удалось — рабочая база сохранена")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def status() -> dict:
    """Состояние модуля для /api/health: готовность базы, число строк, свежесть."""
    updated_at = registry.meta("updated_at")
    age_days: float | None = None
    if updated_at:
        try:
            delta = datetime.now(timezone.utc) - datetime.fromisoformat(updated_at)
            age_days = round(delta.total_seconds() / 86400, 1)
        except ValueError:
            age_days = None
    return {
        "db_ready": registry.available,
        "rows": int(registry.meta("rows") or 0),
        "updated_at": updated_at,
        "age_days": age_days,
    }
