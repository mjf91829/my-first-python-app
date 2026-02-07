"""Pydantic models for PDF API."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentLinkCreate(BaseModel):
    linked_type: Literal["task", "project", "area"]
    linked_id: int


class DocumentLinkRemove(BaseModel):
    linked_type: Literal["task", "project", "area"]
    linked_id: int


class MarkupsSaveBody(BaseModel):
    """Payload for saving markups for a document + context."""
    linked_type: str | None = None  # None = document-level markups
    linked_id: int | None = None
    markups: list[dict[str, Any]] = Field(..., max_length=1000)
