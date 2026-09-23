"""Контракт H3: извлечённые строки и исправленная человеком спецификация."""

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import Model, Positive


class ExtractedLine(Model):
    line_id: str = Field(min_length=1, max_length=64)
    query: str = Field(min_length=1, max_length=2000)
    quantity: Positive | None
    unit: Literal["шт", "м"] | None

    @field_validator("query", "line_id")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Значение не должно быть пустым.")
        return value.strip()


class Extraction(Model):
    lines: list[ExtractedLine] = Field(min_length=1, max_length=50)
    warnings: list[str]

    @field_validator("lines")
    @classmethod
    def unique_lines(cls, value):
        if len({line.line_id for line in value}) != len(value):
            raise ValueError("Идентификаторы строк должны быть уникальны.")
        return value


class UploadResponse(Extraction):
    upload_id: str


class ReviewedLine(ExtractedLine):
    quantity: Positive
    unit: Literal["шт", "м"]


class UploadProposalRequest(Model):
    request_id: UUID
    warehouse_id: str = Field(min_length=1)
    lines: list[ReviewedLine] = Field(min_length=1, max_length=50)

    @field_validator("lines")
    @classmethod
    def unique_lines(cls, value):
        return Extraction.unique_lines(value)
