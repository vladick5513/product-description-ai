import re

from app.card.schemas import NO_DATA, CardDraft, Characteristic, ProductInput

SEO_TITLE_MAX = 70
SEO_DESCRIPTION_MIN = 800
SEO_DESCRIPTION_MAX = 1200
QUERIES_MIN = 3
QUERIES_MAX = 5

# Утверждения без чисел, которые модель чаще всего добавляет «по аналогии» с другими приборами.
RISKY_CLAIMS = {
    r"гаранти": "гарантия",
    r"сертифи": "сертификат",
    r"поверк|поверен": "поверка",
    r"госреестр": "госреестр",
    r"\bгост": "ГОСТ",
    r"взрыв": "взрывозащита",
    r"нержаве": "нержавеющая сталь",
    r"диспле": "дисплей",
}

# Покупатель не должен видеть в тексте рассуждения о входных данных: место пропусков в таблице.
META_TEXT = r"(исходн|входн|предоставленн)\w* (данн|сведен)|\bnull\b|не указан|не заявлен"

# В исходных данных встречаются латинские буквы вместо кириллицы: «MПа» с латинской M.
_LOOKALIKES = str.maketrans("aceopxykmthb", "асеорхукмтнв")


def _normalize(text: str) -> str:
    text = text.lower().replace("ё", "е").replace(" ", " ")
    text = re.sub(r"[‐-―−]", "-", text)
    return re.sub(r"\s+", " ", text).strip().translate(_LOOKALIKES)


def _canonical_number(number: str) -> str:
    number = number.replace(",", ".")
    return number.rstrip("0").rstrip(".") if "." in number else number


def _numbers(text: str) -> set[str]:
    return {_canonical_number(n) for n in re.findall(r"\d+(?:[.,]\d+)?", text)}


def _latin_words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{2,}", text.lower()))


# Значение из описания модель приводит к именительному падежу, поэтому слова сравниваются по
# началу, а числа точно: «нержавеющая сталь» подтверждается фразой «из нержавеющей стали».
def _is_supported(value: str, source: str) -> bool:
    def stems(text: str) -> set[str]:
        return {word[:4] for word in re.findall(r"[а-яa-z]+", text)}

    return _numbers(value) <= _numbers(source) and stems(value) <= stems(source)


def _source_text(product: ProductInput) -> str:
    specs = " ".join(f"{key} {value}" for key, value in product.specs.items())
    return " ".join([product.name, product.manufacturer or "", specs, product.description or ""])


def find_missing_fields(product: ProductInput) -> list[str]:
    missing = []
    if not product.manufacturer:
        missing.append("Производитель (manufacturer)")
    if not product.specs:
        missing.append("Характеристики (specs)")
    if not product.description:
        missing.append("Описание (description)")
    missing += [
        f"Характеристика «{key}»: значение пустое" for key, v in product.specs.items() if not v
    ]
    return missing


# Поля без данных попадают в карточку всегда, а не только когда модель про них вспомнила.
# Пустое значение модель иногда копирует как есть, поэтому оно тоже заменяется кодом.
def add_missing_rows(card: CardDraft, product: ProductInput) -> CardDraft:
    required = [key for key, value in product.specs.items() if not value]
    if not product.manufacturer:
        required.insert(0, "Производитель")
    rows = [
        row if row.value.strip() else Characteristic(name=row.name, value=NO_DATA)
        for row in card.key_characteristics
    ]
    present = {_normalize(row.name) for row in rows}
    extra = [
        Characteristic(name=name, value=NO_DATA)
        for name in required
        if _normalize(name) not in present
    ]
    return card.model_copy(update={"key_characteristics": [*rows, *extra]})


# Без описания фактов может не хватить на минимальный объём. Требовать его от модели значит
# подталкивать её к выдумкам, поэтому короткий текст не исправляется, а только отмечается.
def thin_data_warnings(card: CardDraft, product: ProductInput) -> list[str]:
    length = len(card.seo_description)
    if product.description or length >= SEO_DESCRIPTION_MIN:
        return []
    return [
        f"seo_description: {length} символов при минимуме {SEO_DESCRIPTION_MIN}. "
        "Фактов мало: дополните входные данные и сформируйте карточку заново"
    ]


def _check_format(card: CardDraft, product: ProductInput) -> list[str]:
    problems = []
    title_length = len(card.seo_title)
    if not card.seo_title.strip() or title_length > SEO_TITLE_MAX:
        problems.append(f"seo_title: {title_length} символов, нужно от 1 до {SEO_TITLE_MAX}")
    description_length = len(card.seo_description)
    minimum = SEO_DESCRIPTION_MIN if product.description else 1
    if not minimum <= description_length <= SEO_DESCRIPTION_MAX:
        problems.append(
            f"seo_description: {description_length} символов, "
            f"нужно от {minimum} до {SEO_DESCRIPTION_MAX}"
        )
    queries = {_normalize(query) for query in card.search_queries if query.strip()}
    if not QUERIES_MIN <= len(queries) <= QUERIES_MAX:
        problems.append(
            f"search_queries: {len(queries)} разных запросов, "
            f"нужно от {QUERIES_MIN} до {QUERIES_MAX}"
        )
    if re.search(META_TEXT, _normalize(f"{card.seo_title} {card.seo_description}")):
        problems.append(
            "seo_title и seo_description публикуются на сайте: уберите упоминания исходных "
            "данных и того, что в них не указано"
        )
    if not card.key_characteristics:
        problems.append("key_characteristics: список пуст")
    if not card.commercial_block.target_audience.strip() or not card.commercial_block.tasks:
        problems.append("commercial_block: заполните target_audience и tasks")
    return problems


def _check_characteristics(card: CardDraft, product: ProductInput) -> list[str]:
    source = _normalize(_source_text(product))
    specs = {_normalize(key): value for key, value in product.specs.items()}
    no_data = _normalize(NO_DATA)
    problems = []
    for row in card.key_characteristics:
        value = _normalize(row.value)
        expected = specs.get(_normalize(row.name))
        if expected is not None:
            if value != _normalize(expected or NO_DATA):
                problems.append(
                    f"key_characteristics: «{row.name}» = «{row.value}», "
                    f"во входных данных «{expected or NO_DATA}»"
                )
        elif value != no_data and not _is_supported(value, source):
            problems.append(
                f"key_characteristics: значения «{row.value}» для «{row.name}» "
                "нет во входных данных"
            )
    return problems


def _check_text_facts(card: CardDraft, product: ProductInput) -> list[str]:
    source = _source_text(product)
    text = " ".join(
        [
            card.seo_title,
            card.seo_description,
            *card.search_queries,
            card.commercial_block.target_audience,
            *card.commercial_block.tasks,
        ]
    )
    problems = []
    if numbers := sorted(_numbers(text) - _numbers(source)):
        problems.append(f"в тексте есть числа, которых нет во входных данных: {', '.join(numbers)}")
    if words := sorted(_latin_words(text) - _latin_words(source)):
        problems.append(f"в тексте есть термины, которых нет во входных данных: {', '.join(words)}")
    normalized_text, normalized_source = _normalize(text), _normalize(source)
    for pattern, label in RISKY_CLAIMS.items():
        if re.search(pattern, normalized_text) and not re.search(pattern, normalized_source):
            problems.append(f"в тексте упомянуто «{label}», чего нет во входных данных")
    return problems


def check_card(card: CardDraft, product: ProductInput) -> list[str]:
    return [
        *_check_format(card, product),
        *_check_characteristics(card, product),
        *_check_text_facts(card, product),
    ]
