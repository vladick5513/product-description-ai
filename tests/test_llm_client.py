import json

import httpx2
import openai
import pytest

from app.card.schemas import CardDraft
from app.card.service import CardService
from app.llm.client import LLMClient
from app.llm.exceptions import (
    LLMAPIError,
    LLMAuthError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTransportError,
    LLMUnexpectedResponse,
)
from tests.factories import make_card, make_product

MESSAGES = [{"role": "user", "content": "товар"}]


def completion(content=None, refusal=None, finish_reason="stop") -> dict:
    message = {"role": "assistant", "content": content, "refusal": refusal}
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": "test-model",
        "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
    }


# Настоящий SDK поверх подменённого транспорта: проверяем запрос и разбор ответа без сети.
def make_client(handler) -> LLMClient:
    client = LLMClient("test-key", "test-model")
    client._client = openai.AsyncOpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return client


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, LLMAuthError),
        (403, LLMAuthError),
        (429, LLMRateLimitError),
        (400, LLMAPIError),
        (500, LLMAPIError),
    ],
)
async def test_http_errors_are_wrapped(status, error):
    def handler(request):
        return httpx2.Response(status, json={"error": {"message": "сбой"}})

    with pytest.raises(error) as exc_info:
        await make_client(handler).complete(MESSAGES, CardDraft)
    assert exc_info.value.__cause__ is not None


async def test_connection_error_is_wrapped():
    def handler(request):
        raise httpx2.ConnectError("нет сети")

    with pytest.raises(LLMTransportError):
        await make_client(handler).complete(MESSAGES, CardDraft)


async def test_refusal_is_reported():
    client = make_client(lambda r: httpx2.Response(200, json=completion(refusal="нет")))
    with pytest.raises(LLMRefusalError):
        await client.complete(MESSAGES, CardDraft)


async def test_truncated_answer_is_reported():
    answer = completion(content='{"seo_title": "x', finish_reason="length")
    client = make_client(lambda r: httpx2.Response(200, json=answer))
    with pytest.raises(LLMUnexpectedResponse):
        await client.complete(MESSAGES, CardDraft)


async def test_non_schema_answer_is_reported():
    answer = completion(content='{"seo_title": "x"}')
    client = make_client(lambda r: httpx2.Response(200, json=answer))
    with pytest.raises(LLMUnexpectedResponse):
        await client.complete(MESSAGES, CardDraft)


async def test_repair_turn_sends_valid_history():
    bad = make_card(seo_title="М" * 80).model_dump_json()
    good = make_card().model_dump_json()
    answers = [bad, good]
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx2.Response(200, json=completion(content=answers.pop(0)))

    result = await CardService(make_client(handler)).generate(make_product())

    assert result.status == "ready"
    first, second = bodies
    assert first["model"] == "test-model"
    assert first["response_format"]["type"] == "json_schema"
    assert first["response_format"]["json_schema"]["strict"] is True
    assert [m["role"] for m in second["messages"]] == ["system", "user", "assistant", "user"]
    assert second["messages"][2]["content"] == bad
