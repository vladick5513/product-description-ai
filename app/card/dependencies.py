from typing import Annotated

from fastapi import Depends

from app.card.service import CardService
from app.llm.dependencies import LLMClientDep


async def get_card_service(llm: LLMClientDep) -> CardService:
    return CardService(llm)


CardServiceDep = Annotated[CardService, Depends(get_card_service)]
