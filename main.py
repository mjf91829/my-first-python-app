"""FastAPI task app: tasks stored in JSON, mocked AI suggestion."""

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

TASKS_FILE = Path(__file__).resolve().parent / "tasks.json"


class TaskCreate(BaseModel):
    title: str
    priority: str


class Task(TaskCreate):
    id: int


def load_tasks() -> list[dict]:
    if not TASKS_FILE.exists():
        return []
    with open(TASKS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_tasks(tasks: list[dict]) -> None:
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


def next_id(tasks: list[dict]) -> int:
    if not tasks:
        return 1
    return max(t["id"] for t in tasks) + 1


app = FastAPI(title="Task App")


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("index.html")
    tasks = load_tasks()
    return template.render(request=request, tasks=tasks)


@app.get("/api/tasks")
async def get_tasks():
    return {"tasks": load_tasks()}


@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    tasks = load_tasks()
    new_task = {
        "id": next_id(tasks),
        "title": task.title,
        "priority": task.priority,
    }
    tasks.append(new_task)
    save_tasks(tasks)
    return new_task


@app.get("/api/tasks/{task_id}/suggest")
async def suggest_when(task_id: int):
    """Mock AI suggestion for when to do the task."""
    tasks = load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return {"error": "Task not found"}
    # Mock: suggest based on priority
    suggestions = {
        "high": "Do this today, ideally in the next 2 hours.",
        "medium": "Schedule for this week; block 1–2 hours.",
        "low": "Fit it in when you have spare time or next week.",
    }
    priority = task.get("priority", "medium").lower()
    suggestion = suggestions.get(priority, suggestions["medium"])
    return {"task_id": task_id, "suggestion": suggestion}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
