"""Pydantic models for PDF API."""

from pydantic import BaseModel


class DocumentLinkCreate(BaseModel):
    linked_type: str  # "task" | "project" | "area"
    linked_id: int


class DocumentLinkRemove(BaseModel):
    linked_type: str
    linked_id: int
