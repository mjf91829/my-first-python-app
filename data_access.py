"""Shared data access for PARA app and PDF module."""

import json
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data.json"
TASKS_FILE_LEGACY = Path(__file__).resolve().parent / "tasks.json"
UPLOAD_DIR = Path(__file__).resolve().parent / "documents"


def default_data() -> dict:
    return {
        "projects": [],
        "areas": [],
        "resources": [],
        "archives": [],
        "tasks": [],
        "documents": [],
        "document_links": [],
        "document_markups": [],
    }


def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if "documents" not in data:
            data["documents"] = []
        if "document_links" not in data:
            data["document_links"] = []
        if "document_markups" not in data:
            data["document_markups"] = []
        return data
    data = default_data()
    if TASKS_FILE_LEGACY.exists():
        with open(TASKS_FILE_LEGACY, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list) and raw and "parent_id" not in raw[0]:
            inbox = {"id": 1, "title": "Inbox"}
            data["areas"].append(inbox)
            for t in raw:
                data["tasks"].append({
                    "id": t["id"],
                    "title": t["title"],
                    "priority": t.get("priority", "medium"),
                    "parent_type": "area",
                    "parent_id": 1,
                })
            save_data(data)
        return data
    return data


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def next_id(container_key: str, data: dict) -> int:
    items = data.get(container_key, [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1
