"""Разбор телефона из произвольной строки в структуру PhoneResult.

Шаги: вычленить добавочный номер -> распарсить через phonenumbers -> для РФ обогатить
данными реестра Минцифры, для прочих стран — встроенными базами phonenumbers.
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import phonenumbers
from phonenumbers import Leniency, PhoneNumberMatcher, carrier, geocoder
from phonenumbers import timezone as pn_timezone

from app.modules.phone import geo
from app.modules.phone.models import PhoneResult
from app.modules.phone.registry import registry

# Маркеры добавочного номера в конце строки: «доб.», «доп», «вн», «ext», «x», «*», «#».
_EXT_RE = re.compile(
    r"(?:доб(?:авочный)?|доп(?:олнительный)?|вн(?:утренний)?|ext(?:ension)?|x|\*|#)"
    r"\.?\s*[:№-]?\s*(\d{1,7})\s*$",
    re.IGNORECASE,
)


def _extract_extension(raw: str) -> tuple[str, str]:
    """Отделяет добавочный номер: «846)231.60.14 *139» -> («846)231.60.14», «139»)."""
    m = _EXT_RE.search(raw)
    if m:
        return raw[: m.start()].strip(), m.group(1)
    return raw, ""


def _empty(source: str, qc: int = 1) -> PhoneResult:
    return PhoneResult(
        source=source,
        type="",
        phone="",
        country_code="",
        city_code="",
        number="",
        extension="",
        provider="",
        country="",
        country_iso="",
        region="",
        city="",
        timezone="",
        qc_conflict=0,
        qc=qc,
    )


def _iana_to_utc(tzname: str) -> str:
    """«Europe/Samara» -> «UTC+4». Для зон с дробным смещением — «UTC+5:30»."""
    if not tzname or tzname == "Etc/Unknown":
        return ""
    try:
        offset = datetime.now(ZoneInfo(tzname)).utcoffset()
    except Exception:  # noqa: BLE001
        return ""
    if offset is None:
        return ""
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    hours, minutes = divmod(total // 60, 60)
    return f"UTC{sign}{hours}" + (f":{minutes:02d}" if minutes else "")


def _try_parse(text: str) -> phonenumbers.PhoneNumber | None:
    """Прямой разбор строки. Возвращает номер, если он валиден либо это РФ-номер из 10 цифр."""
    try:
        num = phonenumbers.parse(text, "RU")
    except phonenumbers.NumberParseException:
        return None
    nsn = phonenumbers.national_significant_number(num)
    if phonenumbers.is_valid_number(num) or (num.country_code == 7 and len(nsn) == 10):
        return num
    return None


def _match_in_text(text: str) -> tuple[phonenumbers.PhoneNumber | None, str]:
    """Ищет телефон, встроенный в произвольный текст («грязный» ввод). Берёт первое совпадение."""
    for match in PhoneNumberMatcher(text, "RU", leniency=Leniency.VALID):
        return match.number, (match.number.extension or "")
    return None, ""


# Строка из одних цифр и телефонной пунктуации (без букв) — кандидат на «голый» номер.
_BARE_NUMBER_RE = re.compile(r"^[\s()\-.\d]+$")


def _try_parse_e164(text: str) -> phonenumbers.PhoneNumber | None:
    """Запасной разбор для международного номера, введённого без «+».
    Вызывается только после неудачи основного разбора, поэтому российские номера сюда
    не попадают.
    """
    if not _BARE_NUMBER_RE.match(text):
        return None
    digits = re.sub(r"\D", "", text)
    if not (11 <= len(digits) <= 15):
        return None
    try:
        num = phonenumbers.parse("+" + digits, None)
    except phonenumbers.NumberParseException:
        return None
    return num if phonenumbers.is_valid_number(num) else None


def parse_phone(source: str) -> PhoneResult:
    """Главная точка входа: строка -> PhoneResult."""
    raw = (source or "").strip()
    if not raw:
        return _empty(source, qc=1)

    cleaned, extension = _extract_extension(raw)

    num = _try_parse(cleaned)
    if num is None:
        # Запасной путь 1: вычленить номер из «грязного» текста (слова вокруг номера).
        num, matched_ext = _match_in_text(cleaned)
        if not extension and matched_ext:
            extension = matched_ext
    if num is None:
        # Запасной путь 2: международный номер в E.164 без «+» (напр. номер из СНГ).
        num = _try_parse_e164(cleaned)
    if num is None:
        return _empty(source, qc=1)

    nsn = phonenumbers.national_significant_number(num)
    valid = phonenumbers.is_valid_number(num)
    # Код страны по ISO 3166-1 («RU», «KZ», «US», ...). Важно: +7 — это и Россия,
    # и Казахстан; различать их нужно по региону, а не по коду страны.
    region = phonenumbers.region_code_for_number(num)
    iso = (region or "").lower()

    if region == "RU" and len(nsn) == 10:
        return _parse_ru(source, num, nsn, extension, valid, iso)
    if valid:
        return _parse_intl(source, num, nsn, extension, iso)
    return _empty(source, qc=1)


def _format_phone(num: phonenumbers.PhoneNumber, extension: str) -> str:
    """Международный формат + русский добавочный: «+7 846 231-60-14 доб. 139»."""
    base = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    return f"{base} доб. {extension}" if extension else base


def _parse_ru(
    source: str,
    num: phonenumbers.PhoneNumber,
    nsn: str,
    extension: str,
    valid: bool,
    iso: str,
) -> PhoneResult:
    code = int(nsn[:3])
    number = nsn[3:]

    row = registry.lookup(code, int(number))
    if row:
        provider = row["operator"]
        region, city = geo.parse_territory(row["territory"], row["region"])
        ptype = geo.phone_type(code, row["kind"])
        tz = geo.region_timezone(region)
    else:
        provider = region = city = tz = ""
        ptype = geo.type_ru_from_phonenumbers(phonenumbers.number_type(num)) or "Стационарный"

    # Реестр Минцифры — авторитетный источник: попадание в диапазон валидирует номер.
    qc = 0 if (valid or row) else 1

    return PhoneResult(
        source=source,
        type=ptype,
        phone=_format_phone(num, extension),
        country_code="7",
        city_code=str(code),
        number=number,
        extension=extension,
        provider=provider,
        country="Россия",
        country_iso=iso or "ru",
        region=region,
        city=city,
        timezone=tz,
        qc_conflict=0,
        qc=qc,
    )


def _parse_intl(
    source: str,
    num: phonenumbers.PhoneNumber,
    nsn: str,
    extension: str,
    iso: str,
) -> PhoneResult:
    ndc = phonenumbers.length_of_national_destination_code(num)
    city_code = nsn[:ndc] if ndc > 0 else ""
    number = nsn[ndc:] if ndc > 0 else nsn

    country = geocoder.country_name_for_number(num, "ru")
    provider = carrier.name_for_number(num, "ru")
    city = geocoder.description_for_number(num, "ru")
    # description_for_number может вернуть страну — тогда город не выделяем.
    if city == country:
        city = ""

    # Часовой пояс берём только если он однозначен. Для мобильных номеров
    # phonenumbers возвращает длинный список всех возможных зон — это не пояс города.
    tzs = pn_timezone.time_zones_for_number(num)
    tz = _iana_to_utc(tzs[0]) if len(tzs) == 1 else ""

    return PhoneResult(
        source=source,
        type=geo.type_ru_from_phonenumbers(phonenumbers.number_type(num)),
        phone=_format_phone(num, extension),
        country_code=str(num.country_code),
        city_code=city_code,
        number=number,
        extension=extension,
        provider=provider,
        country=country,
        country_iso=iso,
        region="",
        city=city,
        timezone=tz,
        qc_conflict=0,
        qc=0,
    )
