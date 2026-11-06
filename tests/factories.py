from app.card.schemas import CardDraft, Characteristic, CommercialBlock, ProductInput
from app.llm.client import LLMClient, LLMReply


def make_product(**overrides) -> ProductInput:
    values = {
        "name": "Манометр показывающий DM 02",
        "manufacturer": "Манотомь",
        "specs": {"диапазон измерений": "0–1,6 МПа", "класс точности": "1,5"},
        "description": "Прибор предназначен для измерения избыточного давления.",
    }
    return ProductInput(**{**values, **overrides})


def make_card(**overrides) -> CardDraft:
    values = {
        "seo_title": "Манометр показывающий DM 02, 0–1,6 МПа",
        "seo_description": "Манометр измеряет избыточное давление. " * 25,
        "key_characteristics": [
            Characteristic(name="Производитель", value="Манотомь"),
            Characteristic(name="диапазон измерений", value="0–1,6 МПа"),
            Characteristic(name="класс точности", value="1,5"),
            Characteristic(name="Степень защиты", value="данных нет"),
        ],
        "search_queries": ["манометр dm 02", "манометр 1,6 мпа", "манометр манотомь"],
        "commercial_block": CommercialBlock(
            target_audience="Службы КИП на производстве.", tasks=["Контроль давления в линии"]
        ),
        "clarifications": [],
    }
    return CardDraft(**{**values, **overrides})


class FakeLLM(LLMClient):
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def complete(self, messages, output_format):
        self.calls.append(list(messages))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return LLMReply(parsed=outcome, raw_text=outcome.model_dump_json())
