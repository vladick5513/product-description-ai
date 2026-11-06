import asyncio
import json
from pathlib import Path

from app.card.schemas import ProductInput
from app.card.service import CardService
from app.llm.client import LLMClient
from app.settings import settings

SAMPLES_DIR = Path("samples")
EXAMPLES_DIR = Path("examples")


async def main() -> None:
    llm = LLMClient(settings.OPENAI_API_KEY, settings.LLM_MODEL)
    service = CardService(llm)
    try:
        for sample in sorted(SAMPLES_DIR.glob("*.json")):
            product = ProductInput.model_validate_json(sample.read_text(encoding="utf-8"))
            result = await service.generate(product)
            data = json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
            (EXAMPLES_DIR / f"{sample.stem}.json").write_text(data, encoding="utf-8")
            (EXAMPLES_DIR / f"{sample.stem}.md").write_text(result.markdown, encoding="utf-8")
            print(f"{sample.stem}: {result.status}, предупреждений: {len(result.warnings)}")
    finally:
        await llm.close()


if __name__ == "__main__":
    asyncio.run(main())
