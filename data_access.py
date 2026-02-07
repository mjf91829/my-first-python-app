"""Shared data access for PARA app and PDF module."""

import json
import logging
from pathlib import Path

from filelock import FileLock

DATA_FILE = Path(__file__).resolve().parent / "data.json"
TASKS_FILE_LEGACY = Path(__file__).resolve().parent / "tasks.json"
UPLOAD_DIR = Path(__file__).resolve().parent / "documents"

logger = logging.getLogger(__name__)


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


def _normalize_data(data: dict) -> dict:
    """Ensure required keys exist in data dict."""
    if "documents" not in data:
        data["documents"] = []
    if "document_links" not in data:
        data["document_links"] = []
    if "document_markups" not in data:
        data["document_markups"] = []
    return data


def load_data() -> dict:
    if not DATA_FILE.exists():
        data = default_data()
        if TASKS_FILE_LEGACY.exists():
            try:
                with FileLock(DATA_FILE.with_suffix(".lock")):
                    with open(TASKS_FILE_LEGACY, encoding="utf-8") as f:
                        raw = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not load legacy tasks file: %s", e)
                return data
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

    with FileLock(DATA_FILE.with_suffix(".lock"), shared=True):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.warning("Corrupt data file %s: %s; returning default data", DATA_FILE, e)
            return default_data()
        except OSError as e:
            logger.error("Failed to read data file %s: %s", DATA_FILE, e)
            raise

    return _normalize_data(data)


def save_data(data: dict) -> None:
    tmp = DATA_FILE.with_suffix(".tmp")
    with FileLock(DATA_FILE.with_suffix(".lock")):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp.replace(DATA_FILE)
        except OSError as e:
            logger.error("Failed to save data file %s: %s", DATA_FILE, e)
            raise


def next_id(container_key: str, data: dict) -> int:
    items = data.get(container_key, [])
    if not items:
        return 1
    ids: list[int] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            i = item.get("id")
            if i is not None:
                ids.append(int(i))
        except (TypeError, ValueError):
            continue
    return max(ids, default=0) + 1
