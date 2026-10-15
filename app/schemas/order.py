from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class OrderStatus(StrEnum):
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Category(StrEnum):
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    BOOKS = "books"
    PERSONAL_CARE = "personal_care"


class OrderItem(BaseModel):
    name: str
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)


class Order(BaseModel):
    order_id: int
    customer_email: str
    status: OrderStatus
    category: Category
    items: list[OrderItem] = Field(min_length=1)
    ordered_at: date
    shipped_at: date | None = None
    delivered_at: date | None = None
    tracking_number: str | None = None

    @model_validator(mode="after")
    def check_delivery_date(self) -> Self:
        if self.status is OrderStatus.DELIVERED and self.delivered_at is None:
            raise ValueError(f"Order {self.order_id} is delivered without delivered_at")
        return self


class ReturnPolicy(BaseModel):
    category: Category
    returnable: bool
    window_days: int = Field(ge=0)
    conditions: str


class OrderData(BaseModel):
    orders: list[Order]
    return_policies: list[ReturnPolicy]

    @model_validator(mode="after")
    def check_consistency(self) -> Self:
        order_ids = [order.order_id for order in self.orders]
        if len(order_ids) != len(set(order_ids)):
            raise ValueError("Duplicate order_id in order data")
        if {policy.category for policy in self.return_policies} != set(Category):
            raise ValueError("Every category needs a return policy")
        return self
