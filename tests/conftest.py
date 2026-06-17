"""Общие фикстуры тестов: открытие реестра модуля «телефоны», если база собрана."""

import pytest

from app.modules.phone import source
from app.modules.phone.registry import registry


@pytest.fixture(autouse=True, scope="session")
def _open_registry():
    if source.DB_PATH.exists():
        registry.open()
    yield
