"""Pydantic models for PDF API."""

from typing import Any

from pydantic import BaseModel


class DocumentLinkCreate(BaseModel):
    linked_type: str  # "task" | "project" | "area"
    linked_id: int


class DocumentLinkRemove(BaseModel):
    linked_type: str
    linked_id: int


class MarkupsSaveBody(BaseModel):
    """Payload for saving markups for a document + context."""
    linked_type: str | None = None  # None = document-level markups
    linked_id: int | None = None
    markups: list[dict[str, Any]]  # list of { id, page, type, bounds, color?, text? }
