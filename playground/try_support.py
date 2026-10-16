import asyncio

from app.config.settings import get_settings
from app.core.logger import setup_logging
from app.repositories.order_repository import OrderRepository
from app.services.llm_client import LLMClient
from app.services.support_service import SupportService

CASES = [
    ("sara@example.com", "طلبي رقم 1042 فين؟ وينفع أرجّعه؟"),
    ("sara@example.com", "Where is order 1043?"),
    ("omar@example.com", "Can I still return order 1048?"),
]
SECONDS_BETWEEN_CASES = 15


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    llm_client = LLMClient(settings)
    repository = OrderRepository.from_file(settings.orders_path)
    service = SupportService(llm_client, repository, settings)
    try:
        for index, (customer_email, message) in enumerate(CASES):
            if index:
                await asyncio.sleep(SECONDS_BETWEEN_CASES)
            result = await service.answer(message, customer_email)
            print(f"\n{customer_email}: {message}")
            print(result.model_dump_json(indent=2))
    finally:
        await llm_client.close()


asyncio.run(main())
