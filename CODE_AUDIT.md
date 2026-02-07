# Code Audit Report — PARA Task App

**Auditor role:** Senior Python Architect  
**Scope:** Full application (safety, security, best practices, PARA logic)  
**Date:** 2026-02-07

---

## Critical

### 1. Race conditions and data loss (read-modify-write without locking)

**File:** `data_access.py` (and all callers: `main.py`, `pdf_module/service.py`)  
**Lines:** 23–51 (`load_data`), 54–56 (`save_data`), and every route that does `load_data()` → mutate → `save_data()`.

**Issue:** The app uses a single JSON file with no locking. Two concurrent requests can both `load_data()`, each modify a copy, then both `save_data()` — the last write wins and the other update is lost. This can corrupt or drop data (e.g. one task creation overwritten by another, or document links lost).

**Suggested fix:**

- Introduce file-based locking (e.g. `filelock` or `fcntl.flock`) around the read-modify-write sequence, or
- Use a proper store (SQLite, etc.) with transactions for all mutations.

Example with a simple lock (add to `data_access.py`):

```python
import fcntl  # or use filelock library for cross-platform

def load_data() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            data = json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    # ... rest of normalization ...

def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

On Windows, `fcntl` is not available; use a library like `filelock` for cross-platform locking.

---

### 2. Non-atomic file write risks data corruption

**File:** `data_access.py`  
**Lines:** 54–56

**Issue:** `save_data` writes directly to `data.json`. If the process crashes or the disk fills mid-write, the file can be left truncated or invalid; the next `load_data()` will fail or load bad data.

**Suggested fix:** Write to a temporary file in the same directory, then atomically rename over the target (e.g. `Path.replace()`):

```python
def save_data(data: dict) -> None:
    tmp = DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(DATA_FILE)
```

Use in combination with the locking strategy above (lock before write, write to tmp, replace, then unlock).

---

### 3. Path traversal when serving document files

**File:** `pdf_module/service.py`  
**Lines:** 66–73 (`get_document_path`), 76–88 (`delete_document`)

**Issue:** The path is built as `UPLOAD_DIR / doc["filename"]`. If `data.json` is tampered (or corrupted) and `doc["filename"]` contains `..` segments (e.g. `../../etc/passwd`), the resolved path can point outside `UPLOAD_DIR`, leading to disclosure or deletion of arbitrary files.

**Suggested fix:** Resolve the path and ensure it stays under `UPLOAD_DIR`:

```python
def get_document_path(doc_id: int) -> Path | None:
    doc = get_document(doc_id)
    if not doc:
        return None
    base = UPLOAD_DIR.resolve()
    path = (UPLOAD_DIR / doc["filename"]).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        return None  # path outside UPLOAD_DIR
    return path if path.exists() else None
```

Apply the same containment check in `delete_document` before calling `path.unlink()`.

---

### 4. Unhandled JSON and I/O exceptions

**File:** `data_access.py`  
**Lines:** 25–27 (`load_data`), 36–37 (legacy migration), 54–56 (`save_data`)

**Issue:** `json.load()` can raise `json.JSONDecodeError` on corrupt or invalid JSON. `open()` and file I/O can raise `OSError`/`IOError`. These are unhandled; a bad file or disk error will surface as a 500 and may leave the app in an unclear state.

**Suggested fix:** Catch `json.JSONDecodeError` and `OSError` in `load_data`/`save_data`; log the error; either re-raise a dedicated exception for the route layer to map to 503/500, or in `load_data` return `default_data()` and log when the file is corrupt (depending on product requirements). Avoid swallowing errors without logging.

---

### 5. `next_id` can raise on malformed or mixed-type data

**File:** `data_access.py`  
**Lines:** 58–62

**Issue:** `max(item["id"] for item in items)` assumes every item has an `"id"` key and that all values are comparable (e.g. ints). Missing `"id"` raises `KeyError`; mixed types (e.g. int and str) can raise `TypeError`. This can crash any create/archive endpoint.

**Suggested fix:** Defensive iteration with type coercion and default:

```python
def next_id(container_key: str, data: dict) -> int:
    items = data.get(container_key, [])
    if not items:
        return 1
    ids = []
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
```

---

## Major

### 6. Inconsistent HTTP semantics: success status with error body

**File:** `main.py`  
**Lines:** 147, 190, 219, 236, 276, 279, 281, 347

**Issue:** Several endpoints return HTTP 200 with a body like `{"error": "Project not found"}` instead of 4xx. Examples: `create_area` (147), `create_project` (implicit via similar pattern), `move_to_archive` (190, 219, 236), `create_task` (276, 279, 281), `suggest_when` (347). This breaks REST conventions and makes it hard for clients to handle errors reliably.

**Suggested fix:** Use `HTTPException` and appropriate status codes, e.g.:

- `raise HTTPException(status_code=404, detail="Project not found")` for missing project/area/task.
- `raise HTTPException(status_code=400, detail="Invalid type; use project or area")` for invalid `body.type`.

Apply consistently so every error case returns a single, appropriate status code and optional JSON body (e.g. FastAPI’s default detail).

---

### 7. No upload size limit (DoS)

**File:** `pdf_module/routes.py`  
**Lines:** 13–23

**Issue:** `content = await file.read()` reads the entire file into memory with no size limit. A very large upload can exhaust memory or disk and cause DoS.

**Suggested fix:** Enforce a maximum size (e.g. 50 MB) before or during read. For example, use a wrapper that limits bytes read, or check `Content-Length` and reject before reading (and still cap read size as a safety net). Reject with `HTTPException(413, "File too large")`.

---

### 8. Resource URL can be `javascript:` or other dangerous scheme (XSS)

**File:** `main.py` (model); templates that render resource URLs (e.g. `index.html`)

**Issue:** `ResourceCreate.url` is an unrestricted string. If stored as `javascript:alert(1)` or `data:text/html,...`, the template’s `<a href="${escapeHtml(r.url)}">` still produces a working `javascript:` or `data:` link. Escaping HTML does not prevent the browser from executing the URL when the user clicks the link.

**Suggested fix:** Validate that `url` is either empty or a safe URL (e.g. `http`/`https` only). In Pydantic use a validator or a custom type that only allows `http`/`https` (and optionally relative paths if you support them). Reject others with 400.

---

### 9. Markups payload unbounded (DoS / abuse)

**File:** `pdf_module/models.py`  
**Lines:** 17–22 (`MarkupsSaveBody`)

**Issue:** `markups: list[dict[str, Any]]` has no max length or schema. A client can send a huge array of objects and cause high CPU/memory or storage abuse.

**Suggested fix:** Add a max length (e.g. `Field(..., max_length=1000)`) and optionally a more constrained schema (e.g. a Pydantic model per markup entry with allowed keys). Reject oversized payloads with 400.

---

### 10. Pydantic models lack strict validation (priority, parent_type, type)

**File:** `main.py`  
**Lines:** 36–41 (`TaskCreate`), 49–52 (`ArchiveMoveBody`)

**Issue:** `priority` and `parent_type` are free strings; `ArchiveMoveBody.type` is a free string. Invalid values (e.g. `parent_type="foo"`) are only rejected later in route logic, and some paths return 200 with `{"error": "..."}`.

**Suggested fix:** Use `Literal` (or `Enum`) so invalid values are rejected at validation time with 422:

```python
from typing import Literal

class TaskCreate(BaseModel):
    title: str
    priority: Literal["high", "medium", "low"] = "medium"
    parent_type: Literal["project", "area"]
    parent_id: int

class ArchiveMoveBody(BaseModel):
    type: Literal["project", "area"]
    id: int
```

---

### 11. Import inside route (main app)

**File:** `main.py`  
**Lines:** 56–57, 63–68, 90–91

**Issue:** `from pdf_module.routes import router` and `from pdf_module import service` are done after `app = FastAPI(...)` and inside a route; `_render_template` builds the Jinja environment on every request. This hurts clarity and can add avoidable overhead.

**Suggested fix:** Move all imports to the top of the file. Create the Jinja `Environment` once at module load (or in a lazy singleton) and reuse it in `_render_template`.

---

### 12. Document view uses service without dependency injection

**File:** `main.py`  
**Lines:** 84–102

**Issue:** `document_view` does `from pdf_module import service` and calls `service.get_document(doc_id)` directly. This makes testing and swapping implementations harder and is inconsistent with FastAPI’s dependency style.

**Suggested fix:** Prefer a dependency (e.g. `def get_pdf_service() -> type: return service`) or at least import `service` at module top and use it in the route so tests can patch one place.

---

## Minor

### 13. No type narrowing for `doc_id` in document_view

**File:** `main.py`  
**Lines:** 84–102

**Issue:** After `get_document` and the 404 check, the type of `doc` is still inferred from the function return; the template receives `doc_id` and `doc`. Minor type-safety improvement.

**Suggested fix:** Use an explicit type or assert so the type checker knows `doc` is not None after the 404 branch (e.g. keep the early `raise` and optionally add an assert `assert doc is not None` for the type checker).

---

### 14. Magic strings for parent_type and linked_type

**File:** `main.py`, `pdf_module/service.py`, `pdf_module/routes.py`

**Issue:** Strings like `"project"`, `"area"`, `"task"` are repeated in many places. Typos can cause subtle bugs.

**Suggested fix:** Define constants or an enum (e.g. `PARENT_TYPE_PROJECT = "project"`) and use them everywhere for request/response and storage.

---

### 15. Large file read in upload is synchronous in service layer

**File:** `pdf_module/routes.py`  
**Lines:** 16, 20

**Issue:** `content = await file.read()` is async, but `service.upload_document(content, file.filename)` is synchronous and does file I/O. For large uploads, this blocks the event loop.

**Suggested fix:** Run the CPU/IO-heavy part in a thread pool: `await asyncio.to_thread(service.upload_document, content, file.filename)` so the event loop is not blocked.

---

### 16. PEP 8 / style: two blank lines before top-level definitions

**File:** `main.py`  
**Lines:** 54–56 (optional)

**Issue:** PEP 8 suggests two blank lines before top-level function/class definitions. The block `if STATIC_DIR.exists(): app.mount(...)` is fine; ensure no single blank line appears where two are expected elsewhere.

**Suggested fix:** Run `ruff` or `flake8` and fix any reported spacing; generally use two blank lines before `def`/`class` at module level.

---

### 17. No explicit character limit on text fields

**File:** `main.py` (Pydantic models)

**Issue:** `title`, `goal`, `notes`, `url` etc. have no `max_length`. Extremely long values can bloat JSON and UI and make storage/parsing slower.

**Suggested fix:** Add `Field(..., max_length=500)` (or similar) to title/goal/notes and a higher limit for URL; validate in Pydantic so oversized input returns 422.

---

### 18. PARA logic: archive ID vs container ID

**File:** `main.py`  
**Lines:** 196–197, 221–222

**Issue:** Archive entries get `id: next_id("archives", data)`. The archived container’s original id (project id or area id) is not stored on the archive entry; the UI uses the archive’s own `id`. If you ever need to correlate “this archive came from project 5”, you’d need to add something like `source_id` or `archived_id`. Not a bug, but a design smell if you need that later.

**Suggested fix:** Optional: add `archived_id: int` (or `source_id`) to the archive entry when moving to archive, set to `body.id`, for clearer traceability.

---

### 19. Duplicate route prefix for PDF API

**File:** `main.py`  
**Lines:** 59–60

**Issue:** The PDF router is included with `prefix="/api"`, so PDF routes are under `/api/documents/...`. The main app also defines `@app.get("/api/projects")` etc. This is consistent but worth noting if you later split APIs (e.g. separate “PDF API” prefix).

**Suggested fix:** None required; optional clarity by documenting that all programmatic APIs live under `/api`.

---

### 20. Exception message leaked to client in upload

**File:** `pdf_module/routes.py`  
**Lines:** 22–23

**Issue:** `raise HTTPException(status_code=500, detail=str(e))` exposes internal exception text to the client, which can leak paths or implementation details.

**Suggested fix:** Log the full exception (with traceback) and return a generic message to the client, e.g. `detail="Upload failed"` or a fixed string, and use proper logging for debugging.

---

## Summary

| Severity | Count |
|----------|--------|
| Critical | 5 |
| Major    | 7 |
| Minor    | 8 |

**Priority order for remediation:** Address Critical items first (concurrency/locking, atomic save, path traversal, exception handling, `next_id` robustness), then Major (HTTP semantics, upload size, URL validation, markups limit, Pydantic literals, imports and structure). Minor items can be handled incrementally for maintainability and consistency.
