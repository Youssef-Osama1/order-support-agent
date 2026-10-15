import pytest
from pydantic import ValidationError

from app.schemas.order import Category, Order, OrderData, OrderStatus


def make_order(**overrides):
    order = {
        "order_id": 1,
        "customer_email": "a@example.com",
        "status": "processing",
        "category": "books",
        "items": [{"name": "Book", "quantity": 1, "unit_price": "10.00"}],
        "ordered_at": "2026-10-01",
    }
    return order | overrides


def all_policies():
    return [
        {"category": category, "returnable": True, "window_days": 30, "conditions": "c"}
        for category in Category
    ]


def test_order_parses_enums_and_dates():
    order = Order.model_validate(make_order(status="shipped", shipped_at="2026-10-02"))

    assert order.status is OrderStatus.SHIPPED
    assert order.category is Category.BOOKS
    assert order.shipped_at.isoformat() == "2026-10-02"
    assert order.delivered_at is None


def test_delivered_order_requires_delivered_at():
    with pytest.raises(ValidationError, match="delivered without delivered_at"):
        Order.model_validate(make_order(status="delivered"))


def test_unknown_category_is_rejected():
    with pytest.raises(ValidationError):
        Order.model_validate(make_order(category="toys"))


def test_order_needs_at_least_one_item():
    with pytest.raises(ValidationError):
        Order.model_validate(make_order(items=[]))


@pytest.mark.parametrize("field, value", [("quantity", 0), ("unit_price", "0")])
def test_item_quantity_and_price_must_be_positive(field, value):
    item = {"name": "Book", "quantity": 1, "unit_price": "10.00"} | {field: value}

    with pytest.raises(ValidationError):
        Order.model_validate(make_order(items=[item]))


def test_duplicate_order_ids_are_rejected():
    with pytest.raises(ValidationError, match="Duplicate order_id"):
        OrderData.model_validate(
            {"orders": [make_order(), make_order()], "return_policies": all_policies()}
        )


def test_every_category_needs_a_policy():
    with pytest.raises(ValidationError, match="Every category needs a return policy"):
        OrderData.model_validate(
            {"orders": [make_order()], "return_policies": all_policies()[:-1]}
        )
