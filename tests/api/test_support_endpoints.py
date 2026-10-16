from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_support_service
from app.core.exceptions import AgentStepLimitError, LLMOutputError
from app.main import app
from app.services.agent import AgentResult, ToolCallRecord
from app.services.support_service import SupportService

VALID_BODY = {"message": "Where is order 1044?", "customer_email": "omar@example.com"}


@pytest.fixture
def agent_result():
    return AgentResult(
        reply="Your order has shipped.",
        tool_calls=[
            ToolCallRecord(name="get_order", arguments={"order_id": 1044}, ok=True)
        ],
        steps=2,
    )


@pytest.fixture
def service(agent_result):
    fake = AsyncMock(spec=SupportService)
    fake.answer.return_value = agent_result
    app.dependency_overrides[get_support_service] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_chat_returns_reply_and_trace(client, service):
    response = client.post("/chat", json=VALID_BODY)

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Your order has shipped.",
        "tool_calls": [
            {"name": "get_order", "arguments": {"order_id": 1044}, "ok": True}
        ],
        "steps": 2,
    }


def test_chat_passes_message_and_email_to_service(client, service):
    client.post("/chat", json=VALID_BODY)

    service.answer.assert_awaited_once_with("Where is order 1044?", "omar@example.com")


def test_chat_cleans_message_and_email(client, service):
    client.post(
        "/chat",
        json={"message": "  hello  ", "customer_email": "  Omar@Example.COM "},
    )

    service.answer.assert_awaited_once_with("hello", "omar@example.com")


@pytest.mark.parametrize(
    "body",
    [
        {"message": "   ", "customer_email": "omar@example.com"},
        {"message": "x" * 2_001, "customer_email": "omar@example.com"},
        {"message": "hi", "customer_email": "not-an-email"},
        {"message": "hi", "customer_email": "omar@example"},
        {"message": "hi", "customer_email": "omar @example.com"},
        {"message": "hi"},
        {"customer_email": "omar@example.com"},
    ],
)
def test_invalid_requests_are_rejected(client, service, body):
    response = client.post("/chat", json=body)

    assert response.status_code == 422
    service.answer.assert_not_awaited()


def test_message_at_max_length_is_accepted(client, service):
    response = client.post(
        "/chat", json={"message": "x" * 2_000, "customer_email": "omar@example.com"}
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "error",
    [
        LLMOutputError("Model produced an invalid tool call"),
        AgentStepLimitError("Agent did not finish within 5 steps"),
    ],
)
def test_model_failures_become_502(client, service, error):
    service.answer.side_effect = error

    response = client.post("/chat", json=VALID_BODY)

    assert response.status_code == 502
    assert response.json() == {"detail": str(error)}
