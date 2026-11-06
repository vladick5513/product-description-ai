from app.card.rendering import render_markdown
from app.card.schemas import Characteristic
from app.card.validation import (
    add_missing_rows,
    check_card,
    find_missing_fields,
    thin_data_warnings,
)
from tests.factories import make_card, make_product


def test_valid_card_has_no_problems():
    assert check_card(make_card(), make_product()) == []


def test_title_and_description_length_limits():
    problems = check_card(make_card(seo_title="М" * 71, seo_description="короткий"), make_product())
    assert any("seo_title: 71" in p for p in problems)
    assert any("seo_description: 8 " in p for p in problems)


def test_description_boundaries_are_inclusive():
    for length in (800, 1200):
        card = make_card(seo_description="д" * length)
        assert not any("seo_description" in p for p in check_card(card, make_product()))


def test_short_text_without_description_is_warning_not_repair():
    product = make_product(description=None)
    card = make_card(seo_description="Манометр измеряет давление.")
    assert not any("seo_description" in p for p in check_card(card, product))
    assert any("seo_description" in w for w in thin_data_warnings(card, product))


def test_short_text_with_description_is_sent_to_repair():
    product = make_product()
    card = make_card(seo_description="Манометр измеряет давление.")
    assert any("seo_description" in p for p in check_card(card, product))
    assert thin_data_warnings(card, product) == []


def test_query_count_ignores_duplicates():
    card = make_card(search_queries=["манометр", "Манометр", "манометр "])
    assert any("search_queries: 1 " in p for p in check_card(card, make_product()))


def test_invented_number_in_text_is_reported():
    card = make_card(seo_description="Манометр с классом точности 2,5. " * 30)
    assert any("числа" in p and "2.5" in p for p in check_card(card, make_product()))


def test_same_number_in_other_notation_is_not_reported():
    product = make_product(specs={"давление": "1.60 МПа"})
    card = make_card(
        seo_title="Манометр 1,6 МПа",
        seo_description="Манометр измеряет избыточное давление. " * 25,
        search_queries=["манометр", "манометр 1,6 мпа", "манометр манотомь"],
        key_characteristics=[Characteristic(name="давление", value="1.60 МПа")],
    )
    assert not any("числа" in p for p in check_card(card, product))


def test_invented_latin_term_is_reported():
    card = make_card(seo_description="Манометр с интерфейсом Modbus. " * 30)
    assert any("modbus" in p for p in check_card(card, make_product()))


def test_invented_claim_without_numbers_is_reported():
    card = make_card(seo_description="Манометр имеет сертификат соответствия. " * 25)
    assert any("сертификат" in p for p in check_card(card, make_product()))


def test_claim_present_in_source_is_allowed():
    product = make_product(description="Манометр имеет сертификат соответствия.")
    card = make_card(seo_description="Манометр имеет сертификат соответствия. " * 25)
    assert not any("сертификат" in p for p in check_card(card, product))


def test_changed_spec_value_is_reported():
    card = make_card(key_characteristics=[Characteristic(name="класс точности", value="1,0")])
    assert any("класс точности" in p for p in check_card(card, make_product()))


def test_added_unit_is_reported():
    product = make_product(specs={"Напряжение питания": "24"})
    card = make_card(key_characteristics=[Characteristic(name="Напряжение питания", value="24 В")])
    assert any("Напряжение питания" in p for p in check_card(card, product))


def test_value_from_nowhere_is_reported():
    card = make_card(key_characteristics=[Characteristic(name="Корпус", value="латунь")])
    assert any("латунь" in p for p in check_card(card, make_product()))


def test_value_from_description_may_change_case():
    product = make_product(description="Прибор с мембраной из нержавеющей стали.")
    rows = [Characteristic(name="Материал мембраны", value="нержавеющая сталь")]
    card = make_card(key_characteristics=rows)
    assert not any("Материал мембраны" in p for p in check_card(card, product))


def test_value_with_foreign_number_is_reported_even_if_words_match():
    product = make_product(description="Кабель длиной 2 м.")
    rows = [Characteristic(name="Длина кабеля", value="длина 5 м")]
    card = make_card(key_characteristics=rows)
    assert any("Длина кабеля" in p for p in check_card(card, product))


def test_latin_lookalike_letters_match_cyrillic():
    product = make_product(specs={"диапазон": "0-2,5 MПа"})
    card = make_card(key_characteristics=[Characteristic(name="диапазон", value="0-2,5 МПа")])
    assert not any("диапазон" in p for p in check_card(card, product))


def test_find_missing_fields_lists_absent_and_empty():
    product = make_product(manufacturer=None, description=None, specs={"класс": "", "масса": "1"})
    missing = find_missing_fields(product)
    assert any("manufacturer" in m for m in missing)
    assert any("description" in m for m in missing)
    assert any("«класс»" in m for m in missing)
    assert not any("масса" in m for m in missing)


def test_empty_spec_row_is_added_when_model_skipped_it():
    product = make_product(manufacturer=None, specs={"класс точности": "", "масса": "1"})
    card = add_missing_rows(make_card(key_characteristics=[]), product)
    assert {(r.name, r.value) for r in card.key_characteristics} == {
        ("Производитель", "данных нет"),
        ("класс точности", "данных нет"),
    }


def test_blank_value_from_model_becomes_no_data():
    product = make_product(specs={"класс точности": "", "масса": "1"})
    rows = [Characteristic(name="класс точности", value=" ")]
    card = add_missing_rows(make_card(key_characteristics=rows), product)
    assert [(r.name, r.value) for r in card.key_characteristics] == [
        ("класс точности", "данных нет")
    ]
    assert not any("класс точности" in p for p in check_card(card, product))


def test_meta_text_in_public_description_is_reported():
    card = make_card(seo_description="Производитель в исходных данных не указан. " * 25)
    assert any("публикуются на сайте" in p for p in check_card(card, make_product()))


def test_pipe_in_value_does_not_break_markdown_table():
    rows = [Characteristic(name="Погрешность", value="±(1+0,003·|t|)")]
    markdown = render_markdown(make_card(key_characteristics=rows))
    assert "| Погрешность | ±(1+0,003·\\|t\\|) |" in markdown
