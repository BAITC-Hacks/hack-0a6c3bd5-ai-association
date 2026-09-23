"""Запросы и ответы H2: единый контракт с интерфейсом."""

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import Model, NonNegative, Positive, Product


class SessionRequest(Model):
    pass


class ChatRequest(Model):
    message: str = Field(min_length=1, max_length=4000)
    request_id: UUID
    warehouse_id: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Сообщение не должно быть пустым.")
        return value


class ConfirmRequest(Model):
    request_id: UUID


class CartItem(Model):
    product_id: Positive
    sku: str
    name: str
    unit: Literal["шт", "м"]
    quantity: Positive
    unit_price_kzt: NonNegative
    line_total_kzt: NonNegative


class Cart(Model):
    id: str
    version: NonNegative
    warehouse_id: str | None
    items: list[CartItem]
    total_kzt: NonNegative
    cart_url: Literal["/cart"]
    scope: Literal["local_demo"]


class CheckSource(Model):
    field: str
    value: str


class Check(Model):
    product_id: Positive
    field: str
    expected: str | None
    actual: str | None
    status: Literal["match", "conflict", "unknown"]
    sources: list[CheckSource]


class ProposalItem(Model):
    product_id: Positive
    target_quantity: NonNegative
    unit_price_kzt: NonNegative


class Proposal(Model):
    id: str
    status: Literal["pending", "confirmed", "expired", "superseded"]
    warehouse_id: str
    cart_version: NonNegative
    items: list[ProposalItem]
    result_total_kzt: NonNegative
    expires_at: str


class ChatResponse(Model):
    message: str
    products: list[Product]
    checks: list[Check]
    proposal: Proposal | None
    cart: Cart
    answer_source: Literal["fixture", "rules", "openai"]
    confirmation_required: bool


class ConfirmResponse(Model):
    proposal_id: str
    status: Literal["confirmed"]
    cart: Cart
