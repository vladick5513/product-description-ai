import pytest

from app.card.dependencies import get_card_service
from app.card.schemas import Characteristic
from app.card.service import MAX_ATTEMPTS, CardService
from app.llm.exceptions import LLMAuthError, LLMRateLimitError
from app.main import app
from tests.factories import FakeLLM, make_card

PAYLOAD = {
    "name": "Манометр показывающий DM 02",
    "manufacturer": "Манотомь",
    "specs": {"диапазон измерений": "0–1,6 МПа", "класс точности": "1,5"},
    "description": "Прибор предназначен для измерения избыточного давления.",
}


def use_llm(llm: FakeLLM) -> None:
    async def override() -> CardService:
        return CardService(llm)

    app.dependency_overrides[get_card_service] = override


async def test_complete_data_returns_ready_card(client):
    llm = FakeLLM(make_card())
    use_llm(llm)
    response = await client.post("/cards", json=PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["missing_fields"] == [] and body["warnings"] == []
    assert body["seo_title_length"] == len(body["card"]["seo_title"])
    assert "| класс точности | 1,5 |" in body["markdown"]
    assert len(llm.calls) == 1


async def test_bad_draft_is_sent_back_for_repair(client):
    llm = FakeLLM(make_card(seo_title="М" * 80), make_card())
    use_llm(llm)
    body = (await client.post("/cards", json=PAYLOAD)).json()
    assert body["status"] == "ready" and len(llm.calls) == 2
    assert "seo_title: 80" in llm.calls[1][-1]["content"]


async def test_unfixable_draft_is_returned_with_warnings(client):
    bad = make_card(key_characteristics=[Characteristic(name="Корпус", value="латунь")])
    llm = FakeLLM(*[bad] * MAX_ATTEMPTS)
    use_llm(llm)
    body = (await client.post("/cards", json=PAYLOAD)).json()
    assert body["status"] == "needs_review"
    assert any("латунь" in w for w in body["warnings"])
    assert len(llm.calls) == MAX_ATTEMPTS


async def test_best_attempt_wins_over_last(client):
    best = make_card(seo_title="М" * 80)
    worst = make_card(seo_title="М" * 80, seo_description="коротко")
    use_llm(FakeLLM(best, worst, worst))
    body = (await client.post("/cards", json=PAYLOAD)).json()
    assert len(body["warnings"]) == 1


async def test_incomplete_data_is_reported(client):
    use_llm(FakeLLM(*[make_card()] * MAX_ATTEMPTS))
    payload = {"name": "Манометр", "specs": {"диапазон измерений": "0–1,6 МПа", "класс": ""}}
    body = (await client.post("/cards", json=payload)).json()
    assert body["status"] == "needs_review"
    assert any("manufacturer" in m for m in body["missing_fields"])
    assert any("«класс»" in m for m in body["missing_fields"])
    rows = {r["name"]: r["value"] for r in body["card"]["key_characteristics"]}
    assert rows["класс"] == "данных нет"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "   ", "description": "текст"},
        {"name": "Манометр"},
        {"name": "Манометр", "specs": {"класс": ""}, "description": "  "},
        {"name": "Манометр", "specs": "не объект", "description": "текст"},
        {"name": "Манометр", "manufactuer": "опечатка", "description": "текст"},
    ],
)
async def test_invalid_input_is_rejected_without_llm_call(client, payload):
    llm = FakeLLM()
    use_llm(llm)
    response = await client.post("/cards", json=payload)
    assert response.status_code == 422
    assert llm.calls == []


async def test_malformed_json_is_rejected(client):
    use_llm(FakeLLM())
    response = await client.post(
        "/cards", content='{"name": ', headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "status"),
    [(LLMAuthError("ключ"), 502), (LLMRateLimitError("лимит"), 503)],
)
async def test_llm_errors_map_to_readable_response(client, error, status):
    use_llm(FakeLLM(error))
    response = await client.post("/cards", json=PAYLOAD)
    assert response.status_code == status
    assert response.json()["detail"] == str(error)


async def test_index_page_is_served(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Черновик карточки товара" in response.text
