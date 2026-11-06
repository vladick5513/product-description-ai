from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, JSONResponse

from app.card.router import router as card_router
from app.llm.client import LLMClient
from app.llm.exceptions import LLMError, LLMRateLimitError, LLMTransportError
from app.logger import logger
from app.settings import settings

INDEX_PAGE = Path(__file__).parent / "static" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.llm_client = LLMClient(settings.OPENAI_API_KEY, settings.LLM_MODEL)
    yield
    await app.state.llm_client.close()


app = FastAPI(title="product-description-ai", lifespan=lifespan)
app.include_router(card_router)


# Внешний сбой отдаём понятным сообщением для формы, а не голым 500.
@app.exception_handler(LLMError)
async def handle_llm_error(request: Request, exc: LLMError) -> JSONResponse:
    logger.error("Ошибка LLM: %r", exc)
    temporary = isinstance(exc, LLMRateLimitError | LLMTransportError)
    code = status.HTTP_503_SERVICE_UNAVAILABLE if temporary else status.HTTP_502_BAD_GATEWAY
    return JSONResponse(status_code=code, content={"detail": str(exc)})


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(INDEX_PAGE)
