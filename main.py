"""FastAPI PARA app: Projects, Areas, Resources, Archives; tasks as children of Project or Area."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field, field_validator

from data_access import load_data, next_id, save_data
from pdf_module import service
from pdf_module.routes import router as pdf_router

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

_JINJA_ENV: Environment | None = None


def _get_jinja_env() -> Environment:
    global _JINJA_ENV
    if _JINJA_ENV is None:
        _JINJA_ENV = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        _JINJA_ENV.filters["tojson"] = lambda v: json.dumps(v)
    return _JINJA_ENV


# Pydantic models
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


class ArchiveMoveBody(BaseModel):
    type: Literal["project", "area"]
    id: int


app = FastAPI(title="PARA Task App")

app.include_router(pdf_router, prefix="/api")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _render_template(name: str, request: Request, **kwargs):
    template = _get_jinja_env().get_template(name)
    return template.render(request=request, **kwargs)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    data = load_data()
    return _render_template(
        "index.html",
        request=request,
        projects=data["projects"],
        areas=data["areas"],
        tasks=data["tasks"],
    )


@app.get("/documents/{doc_id}", response_class=HTMLResponse)
async def document_view(
    request: Request,
    doc_id: int,
    linked_type: str | None = None,
    linked_id: int | None = None,
):
    doc = service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    assert doc is not None  # type narrowing for template
    return _render_template(
        "document_view.html",
        request=request,
        doc_id=doc_id,
        doc=doc,
        linked_type=linked_type,
        linked_id=linked_id,
    )


@app.get("/api/projects")
async def get_projects(sort: str | None = None):
    data = load_data()
    projects = list(data["projects"])
    if sort == "deadline":
        projects.sort(key=lambda p: p.get("deadline", ""))
    elif sort == "title":
        projects.sort(key=lambda p: p.get("title", "").lower())
    return {"projects": projects}


@app.post("/api/projects")
async def create_project(project: ProjectCreate):
    data = load_data()
    new_id = next_id("projects", data)
    new_project = {
        "id": new_id,
        "title": project.title,
        "goal": project.goal,
        "deadline": project.deadline,
    }
    data["projects"].append(new_project)
    save_data(data)
    return new_project


@app.get("/api/areas")
async def get_areas(sort: str | None = None, project_id: int | None = None):
    data = load_data()
    areas = list(data["areas"])
    if project_id is not None:
        areas = [a for a in areas if a.get("project_id") == project_id]
    if sort == "title":
        areas.sort(key=lambda a: a.get("title", "").lower())
    return {"areas": areas}


@app.post("/api/areas")
async def create_area(area: AreaCreate):
    data = load_data()
    if area.project_id is not None:
        if not any(p["id"] == area.project_id for p in data["projects"]):
            raise HTTPException(status_code=404, detail="Project not found")
    new_id = next_id("areas", data)
    new_area = {"id": new_id, "title": area.title}
    if area.project_id is not None:
        new_area["project_id"] = area.project_id
    data["areas"].append(new_area)
    save_data(data)
    return new_area


@app.get("/api/resources")
async def get_resources():
    data = load_data()
    return {"resources": data["resources"]}


@app.post("/api/resources")
async def create_resource(resource: ResourceCreate):
    data = load_data()
    new_id = next_id("resources", data)
    new_resource = {
        "id": new_id,
        "title": resource.title,
        "url": resource.url or "",
        "notes": resource.notes or "",
    }
    data["resources"].append(new_resource)
    save_data(data)
    return new_resource


@app.get("/api/archives")
async def get_archives():
    data = load_data()
    return {"archives": data["archives"]}


@app.post("/api/archives/move")
async def move_to_archive(body: ArchiveMoveBody):
    data = load_data()
    if body.type == "project":
        container = next((p for p in data["projects"] if p["id"] == body.id), None)
        if not container:
            raise HTTPException(status_code=404, detail="Project not found")
        nested_areas = [a for a in data["areas"] if a.get("project_id") == body.id]
        area_ids = {a["id"] for a in nested_areas}
        tasks_direct = [t for t in data["tasks"] if t.get("parent_type") == "project" and t.get("parent_id") == body.id]
        tasks_under_areas = [t for t in data["tasks"] if t.get("parent_type") == "area" and t.get("parent_id") in area_ids]
        tasks_snapshot = tasks_direct + tasks_under_areas
        areas_snapshot = [{"id": a["id"], "title": a["title"], "tasks": [t for t in tasks_under_areas if t.get("parent_id") == a["id"]]} for a in nested_areas]
        archive_entry = {
            "id": next_id("archives", data),
            "type": "project",
            "source_id": body.id,
            "title": container["title"],
            "goal": container.get("goal", ""),
            "deadline": container.get("deadline", ""),
            "archived_at": datetime.now(tz=timezone.utc).isoformat(),
            "tasks": tasks_snapshot,
            "areas": areas_snapshot,
        }
        data["archives"].append(archive_entry)
        data["projects"] = [p for p in data["projects"] if p["id"] != body.id]
        data["areas"] = [a for a in data["areas"] if a.get("project_id") != body.id]
        data["tasks"] = [t for t in data["tasks"] if not (
            (t.get("parent_type") == "project" and t.get("parent_id") == body.id) or
            (t.get("parent_type") == "area" and t.get("parent_id") in area_ids)
        )]
        save_data(data)
        return {"ok": True, "archived": archive_entry}
    elif body.type == "area":
        container = next((a for a in data["areas"] if a["id"] == body.id), None)
        if not container:
            raise HTTPException(status_code=404, detail="Area not found")
        tasks_snapshot = [t for t in data["tasks"] if t.get("parent_type") == "area" and t.get("parent_id") == body.id]
        archive_entry = {
            "id": next_id("archives", data),
            "type": "area",
            "source_id": body.id,
            "title": container["title"],
            "goal": "",
            "deadline": "",
            "archived_at": datetime.now(tz=timezone.utc).isoformat(),
            "tasks": tasks_snapshot,
        }
        data["archives"].append(archive_entry)
        data["areas"] = [a for a in data["areas"] if a["id"] != body.id]
        data["tasks"] = [t for t in data["tasks"] if not (t.get("parent_type") == "area" and t.get("parent_id") == body.id)]
        save_data(data)
        return {"ok": True, "archived": archive_entry}
    else:
        raise HTTPException(status_code=400, detail="Invalid type; use project or area")


@app.get("/api/tasks")
async def get_tasks(
    parent_type: str | None = None,
    parent_id: int | None = None,
    priority: str | None = None,
    sort: str | None = None,
):
    data = load_data()
    tasks = list(data["tasks"])
    projects = {p["id"]: p for p in data["projects"]}
    areas = {a["id"]: a for a in data["areas"]}
    if parent_type:
        tasks = [t for t in tasks if t.get("parent_type") == parent_type]
    if parent_id is not None:
        tasks = [t for t in tasks if t.get("parent_id") == parent_id]
    if priority:
        tasks = [t for t in tasks if (t.get("priority") or "medium").lower() == priority.lower()]
    if sort == "deadline":
        def deadline_key(t):
            pt, pid = t.get("parent_type"), t.get("parent_id")
            if pt == "project" and pid and pid in projects:
                return projects[pid].get("deadline", "9999-99-99")
            return "9999-99-99"
        tasks.sort(key=deadline_key)
    elif sort == "priority":
        order = {"high": 0, "medium": 1, "low": 2}
        tasks.sort(key=lambda t: order.get((t.get("priority") or "medium").lower(), 1))
    elif sort == "title":
        tasks.sort(key=lambda t: (t.get("title") or "").lower())
    return {"tasks": tasks, "projects": list(projects.values()), "areas": list(areas.values())}


@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    data = load_data()
    if task.parent_type == "project":
        if not any(p["id"] == task.parent_id for p in data["projects"]):
            raise HTTPException(status_code=404, detail="Project not found")
    elif task.parent_type == "area":
        if not any(a["id"] == task.parent_id for a in data["areas"]):
            raise HTTPException(status_code=404, detail="Area not found")
    new_id = next_id("tasks", data)
    new_task = {
        "id": new_id,
        "title": task.title,
        "priority": task.priority or "medium",
        "parent_type": task.parent_type,
        "parent_id": task.parent_id,
    }
    data["tasks"].append(new_task)
    save_data(data)
    return new_task


@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: int, body: TaskUpdate):
    data = load_data()
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if body.title is not None:
        task["title"] = body.title
    if body.priority is not None:
        task["priority"] = body.priority
    if body.parent_type is not None and body.parent_id is not None:
        if body.parent_type == "project":
            if not any(p["id"] == body.parent_id for p in data["projects"]):
                raise HTTPException(status_code=400, detail="Project not found")
        elif body.parent_type == "area":
            if not any(a["id"] == body.parent_id for a in data["areas"]):
                raise HTTPException(status_code=400, detail="Area not found")
        else:
            raise HTTPException(status_code=400, detail="parent_type must be project or area")
        task["parent_type"] = body.parent_type
        task["parent_id"] = body.parent_id
    elif body.parent_type is not None or body.parent_id is not None:
        raise HTTPException(status_code=400, detail="Must provide both parent_type and parent_id")
    save_data(data)
    return task


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    data = load_data()
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    data["document_links"] = [
        lnk for lnk in data.get("document_links", [])
        if not (lnk.get("linked_type") == "task" and lnk.get("linked_id") == task_id)
    ]
    markups = data.get("document_markups", [])
    data["document_markups"] = [
        m for m in markups
        if not (m.get("linked_type") == "task" and m.get("linked_id") == task_id)
    ]
    save_data(data)
    return {"ok": True}


@app.get("/api/tasks/{task_id}/suggest")
async def suggest_when(task_id: int):
    data = load_data()
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    suggestions = {
        "high": "Do this today, ideally in the next 2 hours.",
        "medium": "Schedule for this week; block 1–2 hours.",
        "low": "Fit it in when you have spare time or next week.",
    }
    priority = (task.get("priority") or "medium").lower()
    suggestion = suggestions.get(priority, suggestions["medium"])
    return {"task_id": task_id, "suggestion": suggestion}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
