"""Shared data access for PARA app and PDF module."""

import json
import logging
from pathlib import Path

from filelock import FileLock

_DATA_DIR = Path(__file__).resolve().parent
DATA_FILE = _DATA_DIR / "data.json"
TASKS_FILE_LEGACY = _DATA_DIR / "archive" / "archive_tasks.json"
TASKS_FILE_LEGACY_ROOT = _DATA_DIR / "tasks.json"  # backward compat: root location
UPLOAD_DIR = _DATA_DIR / "documents"

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


def _get_legacy_tasks_path() -> Path | None:
    """Return path to legacy tasks file if it exists (archive first, then root)."""
    if TASKS_FILE_LEGACY.exists():
        return TASKS_FILE_LEGACY
    if TASKS_FILE_LEGACY_ROOT.exists():
        return TASKS_FILE_LEGACY_ROOT
    return None


def load_data() -> dict:
    if not DATA_FILE.exists():
        data = default_data()
        legacy_path = _get_legacy_tasks_path()
        if legacy_path is not None:
            try:
                with FileLock(DATA_FILE.with_suffix(".lock")):
                    with open(legacy_path, encoding="utf-8") as f:
                        raw = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not load legacy tasks file %s: %s", legacy_path, e)
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
                _write_data(data)
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


def _write_data(data: dict) -> None:
    """Write data to DATA_FILE. Caller must hold the lock if needed."""
    tmp = DATA_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(DATA_FILE)
    except OSError as e:
        logger.error("Failed to save data file %s: %s", DATA_FILE, e)
        raise


def save_data(data: dict) -> None:
    with FileLock(DATA_FILE.with_suffix(".lock")):
        _write_data(data)


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
