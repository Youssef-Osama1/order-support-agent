import json

import pytest

from app.core.exceptions import LLMOutputError
from app.main import handle_llm_output_error

pytestmark = pytest.mark.anyio


async def test_llm_output_error_becomes_502():
    response = await handle_llm_output_error(None, LLMOutputError("refused"))

    assert response.status_code == 502
    assert json.loads(response.body) == {"detail": "refused"}
