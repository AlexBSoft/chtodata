"""Pydantic-модели запроса/ответа. Порядок полей ``PhoneResult`` повторяет формат DaData."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PhoneResult(BaseModel):
    """Результат разбора одного телефона — структура и порядок полей как у DaData."""

    source: str = Field(description="Исходная строка, как пришла на вход")
    type: str = Field(description="Тип: Мобильный / Стационарный / Бесплатный / …")
    phone: str = Field(description="Нормализованный номер, напр. «+7 846 231-60-14 доб. 139»")
    country_code: str = Field(description="Код страны, напр. «7»")
    city_code: str = Field(description="Код города/DEF, напр. «846»")
    number: str = Field(description="Локальный номер без кода города")
    extension: str = Field(description="Добавочный номер")
    provider: str = Field(description="Оператор связи (из реестра Минцифры)")
    country: str = Field(description="Страна, напр. «Россия»")
    country_iso: str = Field(description="Двухбуквенный код страны ISO 3166-1, напр. «ru», «us», «kz»")
    region: str = Field(description="Регион/субъект РФ")
    city: str = Field(description="Город/населённый пункт")
    timezone: str = Field(description="Часовой пояс, напр. «UTC+4»")
    qc_conflict: int = Field(description="Код конфликта (0 — нет конфликтов)")
    qc: int = Field(description="Код качества: 0 — распознан, 1 — не распознан")
