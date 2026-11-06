from typing import Any

from app.card.prompts import SYSTEM_PROMPT, build_repair_message, build_user_message
from app.card.rendering import render_markdown
from app.card.schemas import CardDraft, CardResponse, ProductInput
from app.card.validation import (
    add_missing_rows,
    check_card,
    find_missing_fields,
    thin_data_warnings,
)
from app.llm.client import LLMClient
from app.logger import logger

MAX_ATTEMPTS = 3


class CardService:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def generate(self, product: ProductInput) -> CardResponse:
        missing_fields = find_missing_fields(product)
        card, problems = await self._generate_checked(product, missing_fields)
        problems = [*problems, *thin_data_warnings(card, product)]
        status = "needs_review" if problems or missing_fields or card.clarifications else "ready"
        return CardResponse(
            status=status,
            card=card,
            missing_fields=missing_fields,
            warnings=problems,
            seo_title_length=len(card.seo_title),
            seo_description_length=len(card.seo_description),
            markdown=render_markdown(card),
        )

    # Длину текста и выдуманные значения надёжнее проверить кодом и вернуть модели на исправление.
    # Если за все попытки чисто не вышло, отдаём лучший вариант с предупреждениями: менеджеру
    # полезнее черновик с указанными проблемами, чем ошибка.
    async def _generate_checked(
        self, product: ProductInput, missing_fields: list[str]
    ) -> tuple[CardDraft, list[str]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(product, missing_fields)},
        ]
        best: tuple[CardDraft, list[str]] | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            reply = await self.llm.complete(messages, CardDraft)
            card = add_missing_rows(reply.parsed, product)
            problems = check_card(card, product)
            logger.info("Попытка %s для «%s»: проблем %s", attempt, product.name, len(problems))
            if best is None or len(problems) < len(best[1]):
                best = (card, problems)
            if not problems:
                break
            messages.append({"role": "assistant", "content": reply.raw_text})
            messages.append({"role": "user", "content": build_repair_message(problems)})
        return best
