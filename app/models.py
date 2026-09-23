"""Схемы H1 по docs/API-CONTRACT.md, версия v1."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

NonNegative = Annotated[int, Field(strict=True, ge=0)]
Positive = Annotated[int, Field(strict=True, gt=0)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Property(Model):
    name: str
    value: str
    source_field: str


class Document(Model):
    title: str
    url: str
    kind: Literal["certificate", "datasheet"]


class Snapshot(Model):
    source: Literal["ekt_catalog", "demo_fixture"]
    captured_at: datetime
    source_url: str | None

    @field_validator("captured_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Время снимка должно содержать часовой пояс.")
        from datetime import UTC
        return value.astimezone(UTC)


class Product(Model):
    id: Positive
    sku: str
    name: str
    description: str
    price_kzt: NonNegative | None
    unit: Literal["шт", "м"]
    min_order_quantity: Positive | None
    warehouse_id: str
    available_quantity: NonNegative | None
    total_quantity: NonNegative | None
    properties: list[Property]
    image_url: str | None
    documents: list[Document]
    snapshot: Snapshot


class ProductList(Model):
    items: list[Product]
    total: NonNegative
    limit: Positive
    offset: NonNegative
    warehouse_id: str


class Warehouse(Model):
    id: str
    name: str
    city: str


class Warehouses(Model):
    items: list[Warehouse]
    default_warehouse_id: str


class Health(Model):
    status: Literal["ok"] = "ok"
    api_version: Literal["v1"] = "v1"
    demo_mode: bool
    database: Literal["ok"] = "ok"
