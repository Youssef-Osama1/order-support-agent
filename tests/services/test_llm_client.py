import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import BadRequestError
from pydantic import BaseModel

from app.core.exceptions import LLMOutputError
from app.services.llm_client import LLMClient

pytestmark = pytest.mark.anyio


class Answer(BaseModel):
    text: str


def fake_response(content, finish_reason="stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def fake_parsed_response(parsed, refusal=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(parsed=parsed, refusal=refusal),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


@pytest.fixture
def fake_openai(monkeypatch):
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock()
    sdk.chat.completions.parse = AsyncMock()
    sdk.close = AsyncMock()
    monkeypatch.setattr("app.services.llm_client.AsyncOpenAI", lambda **kwargs: sdk)
    return sdk


@pytest.fixture
def llm(fake_openai, settings):
    return LLMClient(settings)


async def test_complete_returns_model_content(llm, fake_openai):
    fake_openai.chat.completions.create.return_value = fake_response("hello")

    assert await llm.complete("hi") == "hello"


async def test_system_prompt_is_sent_first(llm, fake_openai):
    fake_openai.chat.completions.create.return_value = fake_response("ok")

    await llm.complete("question", system="be brief")

    messages = fake_openai.chat.completions.create.call_args.kwargs["messages"]
    assert messages == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "question"},
    ]


async def test_none_content_becomes_empty_string(llm, fake_openai):
    fake_openai.chat.completions.create.return_value = fake_response(None)

    assert await llm.complete("hi") == ""


async def test_truncated_response_logs_warning(llm, fake_openai, caplog):
    fake_openai.chat.completions.create.return_value = fake_response(
        "cut", finish_reason="length"
    )

    with caplog.at_level(logging.WARNING):
        await llm.complete("hi")

    assert "truncated" in caplog.text


async def test_extract_returns_parsed_object(llm, fake_openai):
    answer = Answer(text="hello")
    fake_openai.chat.completions.parse.return_value = fake_parsed_response(answer)

    assert await llm.extract("hi", Answer) == answer


async def test_extract_sends_schema_as_response_format(llm, fake_openai):
    fake_openai.chat.completions.parse.return_value = fake_parsed_response(
        Answer(text="ok")
    )

    await llm.extract("hi", Answer)

    kwargs = fake_openai.chat.completions.parse.call_args.kwargs
    assert kwargs["response_format"] is Answer


async def test_extract_raises_when_model_refuses(llm, fake_openai):
    fake_openai.chat.completions.parse.return_value = fake_parsed_response(
        None, refusal="I can't help with that"
    )

    with pytest.raises(LLMOutputError, match="can't help"):
        await llm.extract("something bad", Answer)


async def test_extract_raises_when_output_breaks_schema(llm, fake_openai):
    fake_openai.chat.completions.parse.side_effect = BadRequestError(
        "schema mismatch",
        response=httpx.Response(400, request=httpx.Request("POST", "https://test")),
        body={"code": "json_validate_failed"},
    )

    with pytest.raises(LLMOutputError, match="did not match Answer"):
        await llm.extract("hello", Answer)


async def test_extract_reraises_other_bad_requests(llm, fake_openai):
    fake_openai.chat.completions.parse.side_effect = BadRequestError(
        "model not found",
        response=httpx.Response(400, request=httpx.Request("POST", "https://test")),
        body={"code": "model_not_found"},
    )

    with pytest.raises(BadRequestError):
        await llm.extract("hello", Answer)


async def test_close_closes_the_sdk_client(llm, fake_openai):
    await llm.close()

    fake_openai.close.assert_awaited_once()
