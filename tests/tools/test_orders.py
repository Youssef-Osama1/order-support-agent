import json
from datetime import date

import pytest

from app.config.settings import Settings
from app.core.exceptions import ToolError
from app.repositories.order_repository import OrderRepository
from app.schemas.order import Category
from app.tools.orders import (
    CheckReturnEligibilityArgs,
    GetOrderArgs,
    GetReturnPolicyArgs,
    OrderTools,
    return_eligibility,
)

TODAY = date(2026, 10, 15)


@pytest.fixture(scope="module")
def repository():
    settings = Settings(_env_file=None, llm_api_key="k")
    return OrderRepository.from_file(settings.orders_path)


@pytest.fixture
def sara(repository):
    return OrderTools(repository, "sara@example.com", TODAY)


@pytest.fixture
def omar(repository):
    return OrderTools(repository, "omar@example.com", TODAY)


@pytest.fixture
def mona(repository):
    return OrderTools(repository, "mona@example.com", TODAY)


def test_get_order_returns_summary_with_total(sara):
    summary = sara.get_order(1042)

    assert summary["order_id"] == 1042
    assert summary["status"] == "delivered"
    assert summary["delivered_at"] == "2026-10-05"
    assert summary["tracking_number"] == "EG100042"
    assert summary["total"] == "1899.00"


def test_get_order_hides_email_and_empty_fields(mona):
    summary = mona.get_order(1045)

    assert "customer_email" not in summary
    assert "shipped_at" not in summary
    assert "tracking_number" not in summary


def test_get_order_total_sums_all_items(mona):
    assert mona.get_order(1045)["total"] == "1300.00"


def test_tool_results_are_json_serializable(sara):
    json.dumps(sara.get_order(1042))
    json.dumps(sara.check_return_eligibility(1042))
    json.dumps(sara.get_return_policy())


def test_customer_email_match_ignores_case(repository):
    tools = OrderTools(repository, "Sara@Example.COM", TODAY)

    assert tools.get_order(1042)["order_id"] == 1042


@pytest.mark.parametrize("method", ["get_order", "check_return_eligibility"])
def test_other_customers_order_and_missing_order_give_same_error(sara, method):
    with pytest.raises(ToolError) as other_customer:
        getattr(sara, method)(1043)
    with pytest.raises(ToolError) as missing:
        getattr(sara, method)(9043)

    assert str(other_customer.value) == "Order 1043 was not found for this customer"
    assert str(missing.value) == "Order 9043 was not found for this customer"


@pytest.mark.parametrize(
    "customer, order_id, return_by, days_left",
    [
        ("sara", 1041, "2026-10-20", 5),
        ("sara", 1042, "2026-10-19", 4),
        ("omar", 1048, "2026-10-15", 0),
    ],
)
def test_eligible_orders(request, customer, order_id, return_by, days_left):
    result = request.getfixturevalue(customer).check_return_eligibility(order_id)

    assert result["eligible"] is True
    assert result["return_by"] == return_by
    assert result["days_left"] == days_left
    assert result["conditions"]


@pytest.mark.parametrize(
    "customer, order_id, reason",
    [
        ("omar", 1043, "Return window ended on 2026-09-24"),
        ("omar", 1044, "Order is shipped; only delivered orders can be returned"),
        ("mona", 1045, "Order is processing; only delivered orders can be returned"),
        ("mona", 1046, "Order is cancelled; only delivered orders can be returned"),
        ("sara", 1047, "Not returnable for hygiene reasons unless defective."),
    ],
)
def test_ineligible_orders(request, customer, order_id, reason):
    result = request.getfixturevalue(customer).check_return_eligibility(order_id)

    assert result["eligible"] is False
    assert result["reason"] == reason
    assert "days_left" not in result


def test_window_closes_the_day_after_return_by(repository):
    order = repository.find_order(1048)
    policy = repository.get_policy(order.category)

    assert return_eligibility(order, policy, date(2026, 10, 15))["eligible"] is True
    assert return_eligibility(order, policy, date(2026, 10, 16))["eligible"] is False


def test_get_return_policy_for_one_category(sara):
    policies = sara.get_return_policy(Category.ELECTRONICS)["policies"]

    assert policies == [
        {
            "category": "electronics",
            "returnable": True,
            "window_days": 14,
            "conditions": "Unopened or defective, with all original accessories.",
        }
    ]


def test_get_return_policy_without_category_lists_all(sara):
    policies = sara.get_return_policy()["policies"]

    assert {policy["category"] for policy in policies} == set(Category)


@pytest.mark.parametrize("args_model", [GetOrderArgs, CheckReturnEligibilityArgs])
def test_order_args_schema_requires_integer_order_id(args_model):
    schema = args_model.model_json_schema()

    assert schema["required"] == ["order_id"]
    assert schema["properties"]["order_id"]["type"] == "integer"
    assert schema["properties"]["order_id"]["description"]


def test_policy_args_schema_lists_categories_and_is_optional():
    schema = GetReturnPolicyArgs.model_json_schema()

    assert "required" not in schema
    assert schema["$defs"]["Category"]["enum"] == [c.value for c in Category]


def test_order_args_accept_numeric_strings():
    assert GetOrderArgs.model_validate_json('{"order_id": "1042"}').order_id == 1042
