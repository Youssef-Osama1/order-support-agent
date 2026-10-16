import json
import logging
from datetime import date

import pytest
from openai.types.chat import (
    ChatCompletionMessage,
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.chat.chat_completion_message_function_tool_call import Function

from app.core.exceptions import AgentStepLimitError
from app.prompts.support import SUPPORT_SYSTEM_PROMPT
from app.repositories.order_repository import OrderRepository
from app.services.agent import ToolCallRecord
from app.services.support_service import SupportService, build_registry
from app.tools.orders import (
    CheckReturnEligibilityArgs,
    GetOrderArgs,
    GetReturnPolicyArgs,
    OrderTools,
)

pytestmark = pytest.mark.anyio


class FakeLLM:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []

    async def chat(self, messages, tools):
        self.calls.append({"messages": list(messages), "tools": tools})
        return self._replies.pop(0)


def asks(name, arguments):
    return ChatCompletionMessage(
        role="assistant",
        content=None,
        tool_calls=[
            ChatCompletionMessageFunctionToolCall(
                id="call_1",
                type="function",
                function=Function(name=name, arguments=arguments),
            )
        ],
    )


def says(text):
    return ChatCompletionMessage(role="assistant", content=text)


@pytest.fixture
def repository(settings):
    return OrderRepository.from_file(settings.orders_path)


@pytest.fixture
def fixed_settings(settings):
    return settings.model_copy(
        update={"today_override": date(2026, 10, 15), "agent_max_steps": 3}
    )


def make_service(llm, repository, settings):
    return SupportService(llm, repository, settings)


def tool_result(llm, call_index=1):
    tool_message = next(
        m for m in llm.calls[call_index]["messages"] if m["role"] == "tool"
    )
    return json.loads(tool_message["content"])


def test_registry_exposes_the_three_order_tools(repository, settings):
    tools = OrderTools(repository, "sara@example.com", settings.current_date())

    schemas = build_registry(tools).schemas()

    assert [s["function"]["name"] for s in schemas] == [
        "get_order",
        "check_return_eligibility",
        "get_return_policy",
    ]
    assert [s["function"]["parameters"] for s in schemas] == [
        GetOrderArgs.model_json_schema(),
        CheckReturnEligibilityArgs.model_json_schema(),
        GetReturnPolicyArgs.model_json_schema(),
    ]
    assert all(s["function"]["description"] for s in schemas)


def test_no_tool_asks_the_model_for_an_email(repository, settings):
    tools = OrderTools(repository, "sara@example.com", settings.current_date())

    for schema in build_registry(tools).schemas():
        assert "email" not in json.dumps(schema["function"]["parameters"]).lower()


async def test_answer_sends_system_prompt_message_and_tools(repository, settings):
    llm = FakeLLM([says("Hi!")])

    await make_service(llm, repository, settings).answer("hello", "sara@example.com")

    first = llm.calls[0]
    assert first["messages"][0] == {"role": "system", "content": SUPPORT_SYSTEM_PROMPT}
    assert first["messages"][1] == {"role": "user", "content": "hello"}
    assert len(first["tools"]) == 3


async def test_answer_returns_reply_and_trace(repository, settings):
    llm = FakeLLM([asks("get_order", '{"order_id": 1042}'), says("Delivered.")])

    result = await make_service(llm, repository, settings).answer(
        "Where is 1042?", "sara@example.com"
    )

    assert result.reply == "Delivered."
    assert result.steps == 2
    assert result.tool_calls == [
        ToolCallRecord(name="get_order", arguments={"order_id": 1042}, ok=True)
    ]
    assert tool_result(llm)["status"] == "delivered"


async def test_tools_are_bound_to_the_requesting_customer(repository, settings):
    llm = FakeLLM([asks("get_order", '{"order_id": 1043}'), says("Not found.")])

    result = await make_service(llm, repository, settings).answer(
        "Where is 1043?", "sara@example.com"
    )

    assert result.tool_calls[0].ok is False
    assert tool_result(llm) == {"error": "Order 1043 was not found for this customer"}


async def test_same_order_works_for_its_owner(repository, settings):
    llm = FakeLLM([asks("get_order", '{"order_id": 1043}'), says("Delivered.")])

    result = await make_service(llm, repository, settings).answer(
        "Where is 1043?", "Omar@Example.com"
    )

    assert result.tool_calls[0].ok is True


async def test_eligibility_uses_settings_date(repository, fixed_settings):
    llm = FakeLLM(
        [asks("check_return_eligibility", '{"order_id": 1048}'), says("Last day.")]
    )

    await make_service(llm, repository, fixed_settings).answer(
        "Can I return 1048?", "omar@example.com"
    )

    assert tool_result(llm)["days_left"] == 0


async def test_answer_uses_settings_max_steps(repository, fixed_settings):
    llm = FakeLLM([asks("get_order", '{"order_id": 1042}')] * 3)

    with pytest.raises(AgentStepLimitError, match="within 3 steps"):
        await make_service(llm, repository, fixed_settings).answer(
            "loop", "sara@example.com"
        )


async def test_answer_logs_counts_without_customer_data(repository, settings, caplog):
    llm = FakeLLM([asks("get_order", '{"order_id": 1043}'), says("Not found.")])

    with caplog.at_level(logging.INFO):
        await make_service(llm, repository, settings).answer(
            "secret question", "sara@example.com"
        )

    assert "steps=2 tool_calls=1 failed_calls=1" in caplog.text
    assert "sara@example.com" not in caplog.text
    assert "secret question" not in caplog.text
