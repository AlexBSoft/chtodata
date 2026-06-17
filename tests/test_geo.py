"""Тесты гео-логики (чистые функции, без базы)."""

from app.modules.phone import geo


def test_parse_territory_city_and_region():
    assert geo.parse_territory("г.о. Самара|Самарская область") == (
        "Самарская область",
        "Самара",
    )
    assert geo.parse_territory("г.о. город Калининград|Калининградская область") == (
        "Калининградская область",
        "Калининград",
    )
    assert geo.parse_territory(
        "г. Улан-Удэ|г.о. город Улан-Удэ|Республика Бурятия"
    ) == ("Республика Бурятия", "Улан-Удэ")


def test_parse_territory_federal_city():
    assert geo.parse_territory("Город Москва") == ("Москва", "Москва")
    assert geo.parse_territory("Город Санкт-Петербург") == (
        "Санкт-Петербург",
        "Санкт-Петербург",
    )


def test_parse_territory_region_only():
    assert geo.parse_territory("Краснодарский край") == ("Краснодарский край", "")


def test_parse_territory_small_multiregion_takes_first():
    assert geo.parse_territory("Город Москва, Московская область") == ("Москва", "")


def test_parse_territory_tollfree_list_is_empty():
    big = "Республика Адыгея, Республика Башкортостан, Краснодарский край, Москва"
    assert geo.parse_territory(big) == ("", "")
    assert geo.parse_territory("Российская Федерация") == ("", "")


def test_region_timezone():
    assert geo.region_timezone("Самарская область") == "UTC+4"
    assert geo.region_timezone("Москва") == "UTC+3"
    assert geo.region_timezone("Калининградская область") == "UTC+2"
    # Суффикс-уточнение должен срезаться при поиске таймзоны.
    assert geo.region_timezone("Кемеровская область - Кузбасс") == "UTC+7"
    assert geo.region_timezone("Камчатский край") == "UTC+12"
    assert geo.region_timezone("Неизвестный регион") == ""


def test_phone_type():
    assert geo.phone_type(846, "ABC") == "Стационарный"
    assert geo.phone_type(927, "DEF") == "Мобильный"
    assert geo.phone_type(800, "ABC") == "Бесплатный"
