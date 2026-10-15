from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_reads_values_and_hides_api_key():
    settings = Settings(_env_file=None, llm_api_key="secret-key", llm_model="m")

    assert settings.llm_api_key.get_secret_value() == "secret-key"
    assert settings.llm_model == "m"
    assert "secret-key" not in repr(settings)


def test_missing_api_key_fails_fast(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_log_level_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_api_key="k", log_level="INFOO")


def test_orders_path_defaults_to_repo_data_file():
    settings = Settings(_env_file=None, llm_api_key="k")

    assert settings.orders_path.is_absolute()
    assert settings.orders_path.exists()
    assert settings.orders_path.parts[-2:] == ("data", "orders.json")


def test_current_date_uses_override_when_set():
    settings = Settings(_env_file=None, llm_api_key="k", today_override="2026-10-15")

    assert settings.current_date() == date(2026, 10, 15)


def test_current_date_falls_back_to_utc_today(monkeypatch):
    monkeypatch.delenv("TODAY_OVERRIDE", raising=False)
    settings = Settings(_env_file=None, llm_api_key="k")

    assert settings.today_override is None
    assert settings.current_date() == datetime.now(UTC).date()


def test_agent_max_steps_defaults_to_five(monkeypatch):
    monkeypatch.delenv("AGENT_MAX_STEPS", raising=False)

    assert Settings(_env_file=None, llm_api_key="k").agent_max_steps == 5


@pytest.mark.parametrize("steps", [0, 11])
def test_agent_max_steps_out_of_range_is_rejected(steps):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_api_key="k", agent_max_steps=steps)
