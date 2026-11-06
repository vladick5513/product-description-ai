from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NO_DATA = "данных нет"


class ProductInput(BaseModel):
    # Опечатка в имени поля должна быть ошибкой, а не молча потерянными данными.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=500)
    manufacturer: str | None = Field(default=None, max_length=200)
    specs: dict[str, str | int | float | None] = Field(default_factory=dict)
    description: str | None = Field(default=None, max_length=20000)

    @field_validator("specs")
    @classmethod
    def normalize_specs(cls, specs: dict) -> dict[str, str]:
        normalized = {
            key.strip(): "" if value is None else str(value).strip() for key, value in specs.items()
        }
        normalized.pop("", None)
        return normalized

    @model_validator(mode="after")
    def require_facts(self) -> "ProductInput":
        if not self.description and not any(self.specs.values()):
            raise ValueError(
                "Недостаточно данных для карточки: заполните specs или description. "
                "По одному названию сервис карточку не пишет, чтобы не выдумывать характеристики."
            )
        return self


class Characteristic(BaseModel):
    name: str
    value: str


class CommercialBlock(BaseModel):
    target_audience: str
    tasks: list[str]


# Длины здесь не ограничены намеренно: их проверяет validation.py и возвращает модели на
# исправление. Ограничение в схеме превратило бы лишний символ в ошибку всего запроса.
class CardDraft(BaseModel):
    seo_title: str
    seo_description: str
    key_characteristics: list[Characteristic]
    search_queries: list[str]
    commercial_block: CommercialBlock
    clarifications: list[str]


class CardResponse(BaseModel):
    status: Literal["ready", "needs_review"]
    card: CardDraft
    missing_fields: list[str]
    warnings: list[str]
    seo_title_length: int
    seo_description_length: int
    markdown: str
