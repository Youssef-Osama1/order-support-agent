from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.exceptions import ToolError
from app.repositories.order_repository import OrderRepository
from app.schemas.order import Category, Order, OrderStatus, ReturnPolicy


class GetOrderArgs(BaseModel):
    order_id: int = Field(description="Order number the customer mentioned, e.g. 1042")


class CheckReturnEligibilityArgs(BaseModel):
    order_id: int = Field(description="Order number the customer wants to return")


class GetReturnPolicyArgs(BaseModel):
    category: Category | None = Field(
        default=None, description="Product category, or omit for every policy"
    )


class OrderTools:
    def __init__(
        self, repository: OrderRepository, customer_email: str, today: date
    ) -> None:
        self._repository = repository
        self._customer_email = customer_email.casefold()
        self._today = today

    def get_order(self, order_id: int) -> dict:
        return order_summary(self._find_customer_order(order_id))

    def check_return_eligibility(self, order_id: int) -> dict:
        order = self._find_customer_order(order_id)
        policy = self._repository.get_policy(order.category)
        return return_eligibility(order, policy, self._today)

    def get_return_policy(self, category: Category | None = None) -> dict:
        if category is None:
            policies = self._repository.list_policies()
        else:
            policies = [self._repository.get_policy(category)]
        return {"policies": [policy.model_dump(mode="json") for policy in policies]}

    def _find_customer_order(self, order_id: int) -> Order:
        order = self._repository.find_order(order_id)
        if order is None or order.customer_email.casefold() != self._customer_email:
            raise ToolError(f"Order {order_id} was not found for this customer")
        return order


def order_summary(order: Order) -> dict:
    total = sum((item.quantity * item.unit_price for item in order.items), Decimal(0))
    summary = order.model_dump(
        mode="json", exclude={"customer_email"}, exclude_none=True
    )
    return summary | {"total": str(total)}


def return_eligibility(order: Order, policy: ReturnPolicy, today: date) -> dict:
    result = {"order_id": order.order_id, "category": order.category}
    if order.status is not OrderStatus.DELIVERED:
        reason = f"Order is {order.status}; only delivered orders can be returned"
        return result | {"eligible": False, "reason": reason}
    if not policy.returnable:
        return result | {"eligible": False, "reason": policy.conditions}

    return_by = order.delivered_at + timedelta(days=policy.window_days)
    days_left = (return_by - today).days
    if days_left < 0:
        reason = f"Return window ended on {return_by.isoformat()}"
        return result | {"eligible": False, "reason": reason}
    return result | {
        "eligible": True,
        "return_by": return_by.isoformat(),
        "days_left": days_left,
        "conditions": policy.conditions,
    }
