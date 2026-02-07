"""Pydantic models for PDF API."""

from typing import Any

from pydantic import BaseModel, Field

from constants import LinkableType


class DocumentLinkCreate(BaseModel):
    linked_type: LinkableType
    linked_id: int


class DocumentLinkRemove(BaseModel):
    linked_type: LinkableType
    linked_id: int


class MarkupsSaveBody(BaseModel):
    """Payload for saving markups for a document + context."""
    linked_type: str | None = None  # None = document-level markups
    linked_id: int | None = None
    markups: list[dict[str, Any]] = Field(..., max_items=1000)


class SavePdfBody(BaseModel):
    """Payload for save-pdf: context for which markups to bake in."""
    linked_type: str | None = None
    linked_id: int | None = None
