from pathlib import Path

import pytest
from pydantic import ValidationError

from app.repositories.order_repository import OrderRepository
from app.schemas.order import Category, OrderStatus

DATA_PATH = Path(__file__).parents[2] / "data" / "orders.json"


@pytest.fixture
def repository():
    return OrderRepository.from_file(DATA_PATH)


def test_loads_all_orders_and_policies(repository):
    assert all(repository.find_order(i) for i in range(1041, 1049))
    assert {policy.category for policy in repository.list_policies()} == set(Category)


def test_find_order_returns_the_matching_order(repository):
    order = repository.find_order(1042)

    assert order.customer_email == "sara@example.com"
    assert order.status is OrderStatus.DELIVERED
    assert order.category is Category.ELECTRONICS


def test_find_order_returns_none_for_unknown_id(repository):
    assert repository.find_order(9999) is None


def test_get_policy_returns_the_category_policy(repository):
    policy = repository.get_policy(Category.ELECTRONICS)

    assert policy.returnable is True
    assert policy.window_days == 14


def test_personal_care_is_not_returnable(repository):
    assert repository.get_policy(Category.PERSONAL_CARE).returnable is False


def test_from_file_fails_fast_on_invalid_data(tmp_path):
    path = tmp_path / "orders.json"
    path.write_text('{"orders": [], "return_policies": []}', encoding="utf-8")

    with pytest.raises(ValidationError):
        OrderRepository.from_file(path)
