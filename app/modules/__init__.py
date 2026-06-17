"""Реестр модулей обработки данных.

Чтобы добавить новый модуль (например, почта или адреса), создайте пакет
``app/modules/<name>/`` с объектом ``module`` (см. :class:`app.module.Module`)
и добавьте его в список ``MODULES`` ниже. Ядро подключит его автоматически.
"""

from __future__ import annotations

from app.module import Module
from app.modules.phone import module as phone_module

MODULES: list[Module] = [
    phone_module,
]
