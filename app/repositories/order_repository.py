from pathlib import Path
from typing import Self

from app.schemas.order import Category, Order, OrderData, ReturnPolicy


class OrderRepository:
    def __init__(self, data: OrderData) -> None:
        self._orders = {order.order_id: order for order in data.orders}
        self._policies = {policy.category: policy for policy in data.return_policies}

    @classmethod
    def from_file(cls, path: Path) -> Self:
        return cls(OrderData.model_validate_json(path.read_text(encoding="utf-8")))

    def find_order(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)

    def get_policy(self, category: Category) -> ReturnPolicy:
        return self._policies[category]

    def list_policies(self) -> list[ReturnPolicy]:
        return list(self._policies.values())
