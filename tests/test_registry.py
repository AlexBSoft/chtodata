"""Тесты поиска по SQLite-базе реестра (нужна собранная база)."""

import pytest

from app.modules.phone import source
from app.modules.phone.registry import registry

requires_db = pytest.mark.skipif(
    not source.DB_PATH.exists(),
    reason="нет собранной базы — запустите scripts/build_db.py",
)


@requires_db
def test_lookup_samara_hit():
    row = registry.lookup(846, 2316014)
    assert row is not None
    assert row["operator"] == 'ООО "СИПАУТНЭТ"'
    assert row["kind"] == "ABC"
    assert "Самар" in row["territory"]


@requires_db
def test_lookup_narrowest_range_wins():
    # У кода 846 есть и широкий диапазон, и узкие суб-аллокации ФРОНТИР.
    row = registry.lookup(846, 2333111)
    assert row is not None
    assert row["operator"] == 'ООО "ФРОНТИР НЕТВОРК"'


@requires_db
def test_lookup_miss_unknown_code():
    # Код 200 не выделен — попаданий быть не должно.
    assert registry.lookup(200, 1234567) is None


@requires_db
def test_meta_rows_present():
    assert int(registry.meta("rows") or 0) > 400_000
