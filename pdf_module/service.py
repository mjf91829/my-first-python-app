"""PDF document service: upload, list, serve, link/unlink."""

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import re
import uuid

import pikepdf

from constants import AREA, PROJECT, TASK
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


def replace_document(doc_id: int, file_content: bytes) -> dict:
    """
    Overwrite the existing document file with new PDF bytes.
    Validates that the content looks like a PDF and that the document exists.
    Writes to a temp file then replaces the original for safety.
    Returns the document dict; raises ValueError if invalid.
    """
    if not file_content or not file_content.startswith(b"%PDF"):
        raise ValueError("Invalid or empty PDF content")
    doc = get_document(doc_id)
    if not doc:
        raise ValueError("Document not found")
    path = get_document_path(doc_id)
    if not path:
        raise FileNotFoundError("Document file not found")
    ensure_upload_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(file_content)
        tmp.replace(path)
    except OSError as e:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise e
    return doc


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
        if lt == PROJECT and lid in projects:
            title = projects[lid].get("title", "")
        elif lt == AREA and lid in areas:
            title = areas[lid].get("title", "")
        elif lt == TASK and lid in tasks:
            title = tasks[lid].get("title", "")
        if title is not None:
            result.append({"linked_type": lt, "linked_id": lid, "title": title})
    return result


def add_link(doc_id: int, linked_type: str, linked_id: int) -> bool:
    """Add document-PARA link. Returns False if doc not found or PARA item invalid."""
    if linked_type not in (TASK, PROJECT, AREA):
        return False
    data = load_data()
    doc = next((d for d in data["documents"] if d["id"] == doc_id), None)
    if not doc:
        return False
    if linked_type == PROJECT and not any(p["id"] == linked_id for p in data["projects"]):
        return False
    if linked_type == AREA and not any(a["id"] == linked_id for a in data["areas"]):
        return False
    if linked_type == TASK and not any(t["id"] == linked_id for t in data["tasks"]):
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
        if linked_type not in (TASK, PROJECT, AREA):
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


def _validate_markup_context(
    doc_id: int,
    linked_type: str | None,
    linked_id: int | None,
) -> bool:
    """Same validation as set_markups: document exists and context is valid."""
    data = load_data()
    if not get_document(doc_id):
        return False
    if (linked_type is None) != (linked_id is None):
        return False
    if linked_type is not None and linked_id is not None:
        if linked_type not in (TASK, PROJECT, AREA):
            return False
        links = data.get("document_links", [])
        if not any(
            lnk.get("document_id") == doc_id
            and lnk.get("linked_type") == linked_type
            and lnk.get("linked_id") == linked_id
            for lnk in links
        ):
            return False
    return True


def _parse_hex_color(hex_str: str) -> tuple[float, float, float]:
    """Parse #rgb or #rrggbb to (r,g,b) floats 0-1."""
    if not hex_str or not isinstance(hex_str, str):
        return (1.0, 1.0, 0.0)
    m = re.match(r"^#?([a-f0-9]{6})$", hex_str, re.I) or re.match(r"^#?([a-f0-9]{3})$", hex_str, re.I)
    if not m:
        return (1.0, 1.0, 0.0)
    s = m.group(1)
    if len(s) == 3:
        s = s[0] * 2 + s[1] * 2 + s[2] * 2
    return (
        int(s[0:2], 16) / 255,
        int(s[2:4], 16) / 255,
        int(s[4:6], 16) / 255,
    )


def _add_markups_to_pdf(pdf: pikepdf.Pdf, markups_list: list[dict]) -> None:
    """Add markup annotations to pdf pages in place. Does not strip existing annotations."""
    for page_index, page in enumerate(pdf.pages):
        page_markups = [m for m in markups_list if m.get("page") == page_index]
        if not page_markups:
            continue
        try:
            mbox = page.MediaBox
            if hasattr(mbox, "__iter__") and len(mbox) >= 4:
                w = float(mbox[2] - mbox[0])
                h = float(mbox[3] - mbox[1])
            else:
                w, h = 612.0, 792.0
        except Exception:
            w, h = 612.0, 792.0

        if "/Annots" not in page:
            page["/Annots"] = pikepdf.Array()

        for m in page_markups:
            bounds = m.get("bounds") or {}
            x = float(bounds.get("x", 0))
            y = float(bounds.get("y", 0))
            bw = float(bounds.get("width", 0.01))
            bh = float(bounds.get("height", 0.01))
            llx = x * w
            lly = (1 - y - bh) * h
            urx = (x + bw) * w
            ury = (1 - y) * h
            rect = [llx, lly, urx, ury]

            if m.get("type") == "highlight":
                r, g, b = _parse_hex_color(m.get("color") or "#ffeb3b")
                ann = pikepdf.Dictionary(
                    Type=pikepdf.Name.Annot,
                    Subtype=pikepdf.Name.Highlight,
                    Rect=rect,
                    QuadPoints=pikepdf.Array([llx, ury, urx, ury, llx, lly, urx, lly]),
                    C=pikepdf.Array([r, g, b]),
                )
                page["/Annots"].append(pdf.make_indirect(ann))
            elif m.get("type") == "ink":
                pts = m.get("points") or []
                if len(pts) >= 2:
                    stroke = pikepdf.Array()
                    for px, py in pts:
                        stroke.append(float(px) * w)
                        stroke.append((1 - float(py)) * h)
                    ink_list = pikepdf.Array([stroke])
                    ann = pikepdf.Dictionary(
                        Type=pikepdf.Name.Annot,
                        Subtype=pikepdf.Name.Ink,
                        Rect=rect,
                        InkList=ink_list,
                        C=pikepdf.Array(_parse_hex_color(m.get("color") or "#000000")),
                    )
                    page["/Annots"].append(pdf.make_indirect(ann))
            elif m.get("type") == "text":
                text = (m.get("text") or "").strip()
                if text:
                    r, g, b = _parse_hex_color(m.get("color") or "#000000")
                    fs = float(m.get("fontSize") or 12)
                    da = f"/Helv {fs:.1f} Tf {r:.2f} {g:.2f} {b:.2f} rg"
                    ann = pikepdf.Dictionary(
                        Type=pikepdf.Name.Annot,
                        Subtype=pikepdf.Name.FreeText,
                        Rect=rect,
                        Contents=pikepdf.String(text[:500]),
                        DA=pikepdf.String(da),
                    )
                    page["/Annots"].append(pdf.make_indirect(ann))
            elif m.get("type") in ("comment", "sticky_note"):
                ann = pikepdf.Dictionary(
                    Type=pikepdf.Name.Annot,
                    Subtype=pikepdf.Name.Text,
                    Rect=rect,
                    Contents=pikepdf.String(m.get("text") or ""),
                    Name=pikepdf.Name.Comment,
                )
                page["/Annots"].append(pdf.make_indirect(ann))


def build_pdf_with_markups(
    doc_id: int,
    linked_type: str | None = None,
    linked_id: int | None = None,
) -> bytes:
    """
    Build a PDF that includes the given document's content plus current markups as annotations.
    Returns PDF bytes. Raises if document not found or context invalid.
    """
    if not _validate_markup_context(doc_id, linked_type, linked_id):
        raise ValueError("Document not found or invalid markup context")
    path = get_document_path(doc_id)
    if not path:
        raise FileNotFoundError("Document file not found")
    markups_list = get_markups(doc_id, linked_type=linked_type, linked_id=linked_id)

    pdf = pikepdf.Pdf.open(path)
    try:
        _add_markups_to_pdf(pdf, markups_list)
        buf = BytesIO()
        pdf.save(buf)
        return buf.getvalue()
    finally:
        pdf.close()


def build_pdf_with_markups_for_save(
    doc_id: int,
    linked_type: str | None = None,
    linked_id: int | None = None,
) -> bytes:
    """
    Build a PDF for persisting as a new version: strip existing page annotations,
    then add current context's markups from JSON. Use for save-new-version only.
    """
    if not _validate_markup_context(doc_id, linked_type, linked_id):
        raise ValueError("Document not found or invalid markup context")
    path = get_document_path(doc_id)
    if not path:
        raise FileNotFoundError("Document file not found")
    markups_list = get_markups(doc_id, linked_type=linked_type, linked_id=linked_id)

    pdf = pikepdf.Pdf.open(path)
    try:
        for page in pdf.pages:
            if "/Annots" in page:
                page["/Annots"] = pikepdf.Array()
        _add_markups_to_pdf(pdf, markups_list)
        buf = BytesIO()
        pdf.save(buf)
        return buf.getvalue()
    finally:
        pdf.close()


def save_document_pdf_version(
    doc_id: int,
    linked_type: str | None = None,
    linked_id: int | None = None,
) -> dict:
    """
    Build PDF with current context's markups (strip then add), write to a new file,
    and update the document to point to it. Previous filename is appended to doc.versions.
    Returns {"ok": True, "filename": new_filename}. Does not delete the old file.
    """
    if not _validate_markup_context(doc_id, linked_type, linked_id):
        raise ValueError("Document not found or invalid markup context")
    doc = get_document(doc_id)
    if not doc:
        raise ValueError("Document not found")
    pdf_bytes = build_pdf_with_markups_for_save(
        doc_id, linked_type=linked_type, linked_id=linked_id
    )
    original_name = doc.get("original_name", doc.get("filename", "document.pdf"))
    new_filename = safe_filename(original_name)
    out_path = UPLOAD_DIR / new_filename
    ensure_upload_dir()
    out_path.write_bytes(pdf_bytes)

    data = load_data()
    doc_ref = next((d for d in data["documents"] if d["id"] == doc_id), None)
    if not doc_ref:
        raise ValueError("Document not found")
    doc_ref.setdefault("versions", [])
    doc_ref["versions"].append(doc_ref["filename"])
    doc_ref["filename"] = new_filename
    save_data(data)
    return {"ok": True, "filename": new_filename}
