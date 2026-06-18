"""Тесты разбора телефона: эталонный пример DaData и разные форматы ввода."""

import pytest

from app.modules.phone import source
from app.modules.phone.parser import _extract_extension, parse_phone

requires_db = pytest.mark.skipif(
    not source.DB_PATH.exists(),
    reason="нет собранной базы — запустите scripts/build_db.py",
)


@requires_db
def test_reference_example_exact_match():
    """Эталон из ТЗ: ответ должен совпадать с DaData до поля и значения."""
    result = parse_phone("раб 846)231.60.14 *139").model_dump()
    assert result == {
        "source": "раб 846)231.60.14 *139",
        "type": "Стационарный",
        "phone": "+7 846 231-60-14 доб. 139",
        "country_code": "7",
        "city_code": "846",
        "number": "2316014",
        "extension": "139",
        "provider": 'ООО "СИПАУТНЭТ"',
        "country": "Россия",
        "country_iso": "ru",
        "region": "Самарская область",
        "city": "Самара",
        "timezone": "UTC+4",
        "qc_conflict": 0,
        "qc": 0,
    }


def test_extract_extension_forms():
    assert _extract_extension("846)231.60.14 *139") == ("846)231.60.14", "139")
    assert _extract_extension("+7 495 374-77-99 доб. 5") == ("+7 495 374-77-99", "5")
    assert _extract_extension("84952316014 # 12") == ("84952316014", "12")
    assert _extract_extension("84952316014") == ("84952316014", "")


@requires_db
def test_mobile_number():
    r = parse_phone("8 (927) 231-60-14").model_dump()
    assert r["type"] == "Мобильный"
    assert r["country_code"] == "7"
    assert r["city_code"] == "927"
    assert r["number"] == "2316014"
    assert r["qc"] == 0


@requires_db
def test_dirty_text_extraction():
    r = parse_phone("мой телефон 89991234567 звоните").model_dump()
    assert r["qc"] == 0
    assert r["phone"] == "+7 999 123-45-67"
    assert r["country_code"] == "7"


@requires_db
def test_toll_free():
    r = parse_phone("8 800 555 35 35").model_dump()
    assert r["type"] == "Бесплатный"
    assert r["city_code"] == "800"


def test_international_number():
    r = parse_phone("+44 20 7946 0958").model_dump()
    assert r["country_code"] == "44"
    assert r["country"]  # страна определена
    assert r["country_iso"] == "gb"
    assert r["region"] == ""
    assert r["qc"] == 0


def test_foreign_countries_and_iso():
    cases = {
        "+1 212 555 0182": ("us", "1"),
        "+49 30 123456": ("de", "49"),
        "+33 1 42 68 53 00": ("fr", "33"),
        "+380 44 123 4567": ("ua", "380"),
    }
    for src, (iso, cc) in cases.items():
        r = parse_phone(src).model_dump()
        assert r["country_iso"] == iso, src
        assert r["country_code"] == cc, src
        assert r["country"] and r["country"] != "Россия", src
        assert r["qc"] == 0, src


def test_kazakhstan_plus7_is_not_russia():
    """+7 — общий код для РФ и Казахстана; казахский номер не должен стать «Россией»."""
    r = parse_phone("+7 727 250 1234").model_dump()
    assert r["country_iso"] == "kz"
    assert r["country"] == "Казахстан"
    assert r["country"] != "Россия"
    assert r["provider"] == ""  # не ищем в реестре Минцифры
    assert r["qc"] == 0


def test_cis_number_without_plus():
    # Номер из СНГ в E.164 без «+» должен распознаваться, а не считаться битым РФ-номером.
    r = parse_phone("996551606799").model_dump()  # Киргизия
    assert r["qc"] == 0
    assert r["country_code"] == "996"
    assert r["country_iso"] == "kg"
    assert r["phone"] == "+996 551 606 799"


def test_bare_garbage_digits_is_qc1():
    # Длинная строка цифр, не являющаяся валидным номером, остаётся нераспознанной.
    assert parse_phone("123456789012").model_dump()["qc"] == 1


def test_garbage_is_qc1():
    for src in ["не телефон", "", "   ", "abcd"]:
        r = parse_phone(src).model_dump()
        assert r["qc"] == 1
        assert r["phone"] == ""
        assert r["source"] == src
