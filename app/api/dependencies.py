from typing import Annotated

from fastapi import Depends, Request

from app.config.settings import Settings, get_settings
from app.repositories.order_repository import OrderRepository
from app.services.llm_client import LLMClient
from app.services.support_service import SupportService


def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client


LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]


def get_order_repository(request: Request) -> OrderRepository:
    return request.app.state.order_repository


OrderRepositoryDep = Annotated[OrderRepository, Depends(get_order_repository)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_support_service(
    llm_client: LLMClientDep, repository: OrderRepositoryDep, settings: SettingsDep
) -> SupportService:
    return SupportService(llm_client, repository, settings)


SupportServiceDep = Annotated[SupportService, Depends(get_support_service)]
