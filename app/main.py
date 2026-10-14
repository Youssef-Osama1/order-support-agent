from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config.settings import get_settings
from app.core.exceptions import LLMOutputError
from app.core.logger import setup_logging
from app.services.llm_client import LLMClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    app.state.llm_client = LLMClient(settings)
    yield
    await app.state.llm_client.close()


app = FastAPI(title="Order Support Agent", lifespan=lifespan)
app.include_router(api_router)


@app.exception_handler(LLMOutputError)
async def handle_llm_output_error(
    request: Request, error: LLMOutputError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(error)}
    )
