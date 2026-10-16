from fastapi import APIRouter

from app.api.dependencies import SupportServiceDep
from app.api.schemas.support import ChatRequest
from app.services.agent import AgentResult

router = APIRouter()


@router.post("")
async def chat(payload: ChatRequest, service: SupportServiceDep) -> AgentResult:
    return await service.answer(payload.message, payload.customer_email)
