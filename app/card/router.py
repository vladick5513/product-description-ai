from fastapi import APIRouter

from app.card.dependencies import CardServiceDep
from app.card.schemas import CardResponse, ProductInput

router = APIRouter(prefix="/cards", tags=["Карточки товаров"])


@router.post("", response_model=CardResponse)
async def create_card(product: ProductInput, service: CardServiceDep):
    return await service.generate(product)
