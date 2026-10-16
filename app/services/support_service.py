import logging

from app.config.settings import Settings
from app.prompts.support import (
    CHECK_RETURN_ELIGIBILITY_DESCRIPTION,
    GET_ORDER_DESCRIPTION,
    GET_RETURN_POLICY_DESCRIPTION,
    SUPPORT_SYSTEM_PROMPT,
)
from app.repositories.order_repository import OrderRepository
from app.services.agent import AgentResult, Tool, ToolRegistry, run_agent
from app.services.llm_client import LLMClient
from app.tools.orders import (
    CheckReturnEligibilityArgs,
    GetOrderArgs,
    GetReturnPolicyArgs,
    OrderTools,
)

logger = logging.getLogger(__name__)


class SupportService:
    def __init__(
        self, llm_client: LLMClient, repository: OrderRepository, settings: Settings
    ) -> None:
        self._llm_client = llm_client
        self._repository = repository
        self._settings = settings

    async def answer(self, message: str, customer_email: str) -> AgentResult:
        tools = OrderTools(
            self._repository, customer_email, self._settings.current_date()
        )
        result = await run_agent(
            llm_client=self._llm_client,
            registry=build_registry(tools),
            system=SUPPORT_SYSTEM_PROMPT,
            message=message,
            max_steps=self._settings.agent_max_steps,
        )
        logger.info(
            "Answered support message: steps=%s tool_calls=%s failed_calls=%s",
            result.steps,
            len(result.tool_calls),
            sum(not call.ok for call in result.tool_calls),
        )
        return result


def build_registry(tools: OrderTools) -> ToolRegistry:
    return ToolRegistry(
        [
            Tool("get_order", GET_ORDER_DESCRIPTION, GetOrderArgs, tools.get_order),
            Tool(
                "check_return_eligibility",
                CHECK_RETURN_ELIGIBILITY_DESCRIPTION,
                CheckReturnEligibilityArgs,
                tools.check_return_eligibility,
            ),
            Tool(
                "get_return_policy",
                GET_RETURN_POLICY_DESCRIPTION,
                GetReturnPolicyArgs,
                tools.get_return_policy,
            ),
        ]
    )
