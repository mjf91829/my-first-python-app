"""PDF document service: upload, list, serve, link/unlink."""

from datetime import datetime, timezone
from pathlib import Path
import re
import uuid

from data_access import UPLOAD_DIR, load_data, next_id, save_data


def ensure_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def safe_filename(original: str) -> str:
    """Generate a safe stored filename using UUID prefix."""
    ext = Path(original).suffix or ".pdf"
    if ext.lower() != ".pdf":
        ext = ".pdf"
    base = re.sub(r"[^\w\-.]", "_", Path(original).stem)[:80] or "document"
    return f"{uuid.uuid4().hex[:12]}_{base}{ext}"


def upload_document(file_content: bytes, original_filename: str) -> dict:
    """Save PDF file and create document record. Returns document dict or raises."""
    ensure_upload_dir()
    stored_name = safe_filename(original_filename)
    path = UPLOAD_DIR / stored_name
    path.write_bytes(file_content)

    data = load_data()
    doc_id = next_id("documents", data)
    doc = {
        "id": doc_id,
        "filename": stored_name,
        "original_name": original_filename,
        "uploaded_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    data["documents"].append(doc)
    save_data(data)
    return doc


def list_documents(linked_type: str | None = None, linked_id: int | None = None) -> list[dict]:
    """List documents, optionally filtered by linked PARA item."""
    data = load_data()
    docs = list(data.get("documents", []))
    links = data.get("document_links", [])

    if linked_type and linked_id is not None:
        linked_doc_ids = {
            lnk["document_id"]
            for lnk in links
            if lnk.get("linked_type") == linked_type and lnk.get("linked_id") == linked_id
        }
        docs = [d for d in docs if d["id"] in linked_doc_ids]

    return docs


def get_document(doc_id: int) -> dict | None:
    """Get document metadata by id."""
    data = load_data()
    return next((d for d in data.get("documents", []) if d["id"] == doc_id), None)


def _path_under_upload_dir(path: Path) -> bool:
    """Return True if path resolves to a location under UPLOAD_DIR."""
    base = UPLOAD_DIR.resolve()
    try:
        path.resolve().relative_to(base)
        return True
    except ValueError:
        return False


def get_document_path(doc_id: int) -> Path | None:
    """Get filesystem path for document file, or None if not found or path traversal."""
    doc = get_document(doc_id)
    if not doc:
        return None
    path = (UPLOAD_DIR / doc["filename"]).resolve()
    if not _path_under_upload_dir(path):
        return None
    return path if path.exists() else None


def delete_document(doc_id: int) -> bool:
    """Delete document record and file. Returns True if deleted."""
    data = load_data()
    doc = next((d for d in data["documents"] if d["id"] == doc_id), None)
    if not doc:
        return False
    path = (UPLOAD_DIR / doc["filename"]).resolve()
    if path.exists() and _path_under_upload_dir(path):
        path.unlink()
    data["documents"] = [d for d in data["documents"] if d["id"] != doc_id]
    data["document_links"] = [lnk for lnk in data["document_links"] if lnk.get("document_id") != doc_id]
    data["document_markups"] = [m for m in data.get("document_markups", []) if m.get("document_id") != doc_id]
    save_data(data)
    return True


def get_linked_items(doc_id: int) -> list[dict]:
    """Get list of linked PARA items for a document: {type, id, title}."""
    data = load_data()
    links = [lnk for lnk in data.get("document_links", []) if lnk.get("document_id") == doc_id]
    projects = {p["id"]: p for p in data.get("projects", [])}
    areas = {a["id"]: a for a in data.get("areas", [])}
    tasks = {t["id"]: t for t in data.get("tasks", [])}

    result = []
    for lnk in links:
        lt, lid = lnk.get("linked_type"), lnk.get("linked_id")
        title = None
        if lt == "project" and lid in projects:
            title = projects[lid].get("title", "")
        elif lt == "area" and lid in areas:
            title = areas[lid].get("title", "")
        elif lt == "task" and lid in tasks:
            title = tasks[lid].get("title", "")
        if title is not None:
            result.append({"linked_type": lt, "linked_id": lid, "title": title})
    return result


def add_link(doc_id: int, linked_type: str, linked_id: int) -> bool:
    """Add document-PARA link. Returns False if doc not found or PARA item invalid."""
    if linked_type not in ("task", "project", "area"):
        return False
    data = load_data()
    doc = next((d for d in data["documents"] if d["id"] == doc_id), None)
    if not doc:
        return False
    if linked_type == "project" and not any(p["id"] == linked_id for p in data["projects"]):
        return False
    if linked_type == "area" and not any(a["id"] == linked_id for a in data["areas"]):
        return False
    if linked_type == "task" and not any(t["id"] == linked_id for t in data["tasks"]):
        return False
    if any(lnk.get("document_id") == doc_id and lnk.get("linked_type") == linked_type and lnk.get("linked_id") == linked_id for lnk in data["document_links"]):
        return True  # already linked
    data["document_links"].append({"document_id": doc_id, "linked_type": linked_type, "linked_id": linked_id})
    save_data(data)
    return True


def remove_link(doc_id: int, linked_type: str, linked_id: int) -> bool:
    """Remove document-PARA link."""
    data = load_data()
    before = len(data["document_links"])
    data["document_links"] = [
        lnk for lnk in data["document_links"]
        if not (lnk.get("document_id") == doc_id and lnk.get("linked_type") == linked_type and lnk.get("linked_id") == linked_id)
    ]
    if len(data["document_links"]) < before:
        save_data(data)
        return True
    return False


def get_documents_for_para(linked_type: str, linked_id: int) -> list[dict]:
    """List documents linked to a project, area, or task."""
    return list_documents(linked_type=linked_type, linked_id=linked_id)


def _markup_record_key(rec: dict) -> tuple[int | None, str | None, int | None]:
    """(document_id, linked_type, linked_id) for matching. None means document-level."""
    return (
        rec.get("document_id"),
        rec.get("linked_type"),
        rec.get("linked_id"),
    )


def get_markups(
    doc_id: int,
    linked_type: str | None = None,
    linked_id: int | None = None,
) -> list[dict]:
    """
    Get markups for a document and optional context.
    If linked_type/linked_id are None, return document-level markups.
    Returns the markups array (list of annotation objects); empty list if no record.
    """
    data = load_data()
    if not get_document(doc_id):
        return []
    records = data.get("document_markups", [])
    for rec in records:
        if _markup_record_key(rec) == (doc_id, linked_type, linked_id):
            return list(rec.get("markups", []))
    return []


def set_markups(
    doc_id: int,
    markups: list[dict],
    linked_type: str | None = None,
    linked_id: int | None = None,
) -> bool:
    """
    Save markups for a document + context.
    If linked_type and linked_id are both provided, validates that this doc is linked to that item.
    If both are None, allows document-level markups.
    Returns True on success, False if validation fails.
    """
    data = load_data()
    if not get_document(doc_id):
        return False
    # Context must be both provided (linked item) or both None (document-level).
    if (linked_type is None) != (linked_id is None):
        return False
    if linked_type is not None and linked_id is not None:
        if linked_type not in ("task", "project", "area"):
            return False
        links = data.get("document_links", [])
        if not any(
            lnk.get("document_id") == doc_id
            and lnk.get("linked_type") == linked_type
            and lnk.get("linked_id") == linked_id
            for lnk in links
        ):
            return False
    records = data.get("document_markups", [])
    key = (doc_id, linked_type, linked_id)
    new_rec = {
        "document_id": doc_id,
        "linked_type": linked_type,
        "linked_id": linked_id,
        "markups": markups,
    }
    # Remove existing record for this (doc_id, linked_type, linked_id)
    records = [r for r in records if _markup_record_key(r) != key]
    records.append(new_rec)
    data["document_markups"] = records
    save_data(data)
    return True
