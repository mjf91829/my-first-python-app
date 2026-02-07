"""Pydantic models for PDF API."""

import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator

from constants import LinkableType


def _validate_hex_color(v: str) -> str:
    if not v or not isinstance(v, str):
        return "#000000"
    m = re.match(r"^#?([a-f0-9]{6})$", v, re.I) or re.match(r"^#?([a-f0-9]{3})$", v, re.I)
    if not m:
        raise ValueError("color must be hex format (#rgb or #rrggbb)")
    return v if v.startswith("#") else f"#{v}"


class BoundsBase(BaseModel):
    """Normalized bounds (0-1) for markup position."""

    x: Annotated[float, Field(ge=0, le=1)]
    y: Annotated[float, Field(ge=0, le=1)]
    width: Annotated[float, Field(ge=0, le=1)]
    height: Annotated[float, Field(ge=0, le=1)]

    @field_validator("x", "y", "width", "height", mode="before")
    @classmethod
    def clamp_bounds(cls, v: float) -> float:
        f = float(v)
        return max(0.0, min(1.0, f))


class HighlightMarkup(BaseModel):
    """Highlight annotation markup."""

    type: Literal["highlight"]
    id: str
    page: int
    bounds: BoundsBase
    color: str = "#ffeb3b"

    @field_validator("color", mode="before")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return _validate_hex_color(v or "#ffeb3b")


class InkMarkup(BaseModel):
    """Ink/freehand annotation markup."""

    type: Literal["ink"]
    id: str
    page: int
    bounds: BoundsBase
    points: list[list[float]]
    color: str = "#000000"
    strokeWidth: float = Field(default=2, alias="strokeWidth", ge=0.5, le=20)

    @field_validator("color", mode="before")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return _validate_hex_color(v or "#000000")

    @field_validator("points")
    @classmethod
    def validate_points(cls, v: list[list[float]]) -> list[list[float]]:
        if len(v) > 2000:
            raise ValueError("ink points must not exceed 2000")
        for pt in v:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                raise ValueError("each point must be [x, y]")
        return v

    model_config = {"populate_by_name": True}


class TextMarkup(BaseModel):
    """Text annotation markup."""

    type: Literal["text"]
    id: str
    page: int
    bounds: BoundsBase
    text: str = ""
    fontSize: float = Field(default=12, alias="fontSize", ge=6, le=72)
    color: str = "#000000"

    @field_validator("color", mode="before")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return _validate_hex_color(v or "#000000")

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if len(v) > 2000:
            raise ValueError("text must not exceed 2000 characters")
        return v

    model_config = {"populate_by_name": True}


class CommentMarkup(BaseModel):
    """Comment/sticky-note annotation markup."""

    type: Literal["comment", "sticky_note"]
    id: str
    page: int
    bounds: BoundsBase
    text: str = ""

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if len(v) > 2000:
            raise ValueError("comment text must not exceed 2000 characters")
        return v


MarkupItem = Annotated[
    Union[HighlightMarkup, InkMarkup, TextMarkup, CommentMarkup],
    Field(discriminator="type"),
]


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
    markups: list[MarkupItem] = Field(..., max_length=1000)


class SavePdfBody(BaseModel):
    """Payload for save-pdf: context for which markups to bake in."""

    linked_type: str | None = None
    linked_id: int | None = None
