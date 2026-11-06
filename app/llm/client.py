from dataclasses import dataclass
from typing import Any

import openai
from pydantic import BaseModel, ValidationError

from app.llm.exceptions import (
    LLMAPIError,
    LLMAuthError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTransportError,
    LLMUnexpectedResponse,
)
from app.logger import logger

REQUEST_TIMEOUT_SECONDS = 120.0


@dataclass
class LLMReply[T: BaseModel]:
    parsed: T
    raw_text: str


class LLMClient:
    def __init__(self, api_key: str, model: str):
        self.model = model
        self._client = openai.AsyncOpenAI(
            api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=2
        )

    async def close(self) -> None:
        await self._client.close()

    async def complete[T: BaseModel](
        self, messages: list[dict[str, Any]], output_format: type[T]
    ) -> LLMReply[T]:
        try:
            response = await self._client.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=output_format,
            )
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise LLMAuthError("LLM API отклонил ключ: проверьте OPENAI_API_KEY") from exc
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(
                "Превышен лимит запросов к LLM или закончились средства на счёте API"
            ) from exc
        except openai.APIStatusError as exc:
            raise LLMAPIError(f"LLM API вернул HTTP {exc.status_code}: {exc.message}") from exc
        except openai.APIConnectionError as exc:
            raise LLMTransportError("Не удалось связаться с LLM API, повторите позже") from exc
        except openai.LengthFinishReasonError as exc:
            raise LLMUnexpectedResponse("Ответ LLM обрезан по лимиту токенов") from exc
        except openai.ContentFilterFinishReasonError as exc:
            raise LLMRefusalError("Ответ LLM заблокирован фильтром контента") from exc
        except ValidationError as exc:
            raise LLMUnexpectedResponse("LLM вернула данные не по схеме") from exc

        if not response.choices:
            raise LLMUnexpectedResponse("В ответе LLM нет карточки")
        message = response.choices[0].message
        logger.info(
            "LLM %s: request_id=%s finish=%s usage=%s",
            response.model,
            response._request_id,
            response.choices[0].finish_reason,
            response.usage,
        )
        if message.refusal:
            raise LLMRefusalError(f"LLM отказалась обрабатывать запрос: {message.refusal}")
        if message.parsed is None or message.content is None:
            raise LLMUnexpectedResponse("В ответе LLM нет карточки")
        return LLMReply(parsed=message.parsed, raw_text=message.content)
