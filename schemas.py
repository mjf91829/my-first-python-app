"""Pydantic request/response models for PARA API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    title: str = Field(..., max_length=500)
    goal: str = Field(default="", max_length=500)
    deadline: str = Field(default="", max_length=100)


class AreaCreate(BaseModel):
    title: str = Field(..., max_length=500)
    project_id: int | None = None


class ResourceCreate(BaseModel):
    title: str = Field(..., max_length=500)
    url: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=500)

    @field_validator("url")
    @classmethod
    def url_must_be_http_or_https(cls, v: str) -> str:
        if not v:
            return v
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class TaskCreate(BaseModel):
    title: str = Field(..., max_length=500)
    priority: Literal["high", "medium", "low"] = "medium"
    parent_type: Literal["project", "area"]
    parent_id: int


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    priority: Literal["high", "medium", "low"] | None = None
    parent_type: Literal["project", "area"] | None = None
    parent_id: int | None = None
    completed: bool | None = None


class ArchiveMoveBody(BaseModel):
    type: Literal["project", "area"]
    id: int
