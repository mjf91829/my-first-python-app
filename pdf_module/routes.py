"""FastAPI routes for PDF documents."""

import asyncio
import logging

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from constants import AREA, PROJECT, TASK
from pdf_module.models import DocumentLinkCreate, DocumentLinkRemove, MarkupsSaveBody, SavePdfBody
from pdf_module import service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pdf"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
CHUNK_SIZE = 64 * 1024  # 64 KB


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    content_length = file.size if hasattr(file, "size") else None
    if content_length is not None and content_length > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        doc = await asyncio.to_thread(service.upload_document, content, file.filename)
        return doc
    except Exception:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail="Upload failed")


@router.get("/documents")
async def list_documents(linked_type: str | None = None, linked_id: int | None = None):
    docs = service.list_documents(linked_type=linked_type, linked_id=linked_id)
    return {"documents": docs}


@router.get("/documents/{doc_id}")
async def get_document(doc_id: int):
    doc = service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    linked = service.get_linked_items(doc_id)
    return {"document": doc, "linked": linked}


@router.get("/documents/{doc_id}/file")
async def serve_document_file(doc_id: int):
    path = service.get_document_path(doc_id)
    if not path:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = service.get_document(doc_id)
    filename = doc.get("original_name", doc.get("filename", "document.pdf"))
    # Strip control characters (incl. \r, \n) to prevent header injection
    safe_filename = "".join(c for c in filename if ord(c) >= 32 and ord(c) != 127)
    if not safe_filename:
        safe_filename = "document.pdf"
    safe_filename = safe_filename.replace("\\", "\\\\").replace('"', '\\"')
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_filename}"'},
    )


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int):
    if not service.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"ok": True}


@router.post("/documents/{doc_id}/link")
async def add_document_link(doc_id: int, body: DocumentLinkCreate):
    if not service.add_link(doc_id, body.linked_type, body.linked_id):
        raise HTTPException(status_code=400, detail="Invalid link or document/PARA item not found")
    return {"ok": True}


@router.delete("/documents/{doc_id}/link")
async def remove_document_link(doc_id: int, body: DocumentLinkRemove):
    service.remove_link(doc_id, body.linked_type, body.linked_id)
    return {"ok": True}


@router.get("/para/{linked_type}/{linked_id}/documents")
async def get_para_documents(linked_type: str, linked_id: int):
    if linked_type not in (TASK, PROJECT, AREA):
        raise HTTPException(status_code=400, detail=f"linked_type must be {TASK}, {PROJECT}, or {AREA}")
    docs = service.get_documents_for_para(linked_type, linked_id)
    return {"documents": docs}


@router.get("/documents/{doc_id}/markups")
async def get_document_markups(
    doc_id: int,
    linked_type: str | None = None,
    linked_id: int | None = None,
):
    """Get markups for a document and optional context. Omitted context = document-level markups."""
    if service.get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    markups = service.get_markups(doc_id, linked_type=linked_type, linked_id=linked_id)
    return {"markups": markups}


@router.put("/documents/{doc_id}/markups")
async def save_document_markups(doc_id: int, body: MarkupsSaveBody):
    """Save markups for a document + context. Body.linked_type/linked_id None = document-level."""
    if service.get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not service.set_markups(
        doc_id,
        body.markups,
        linked_type=body.linked_type,
        linked_id=body.linked_id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid context or (linked_type, linked_id) not linked to this document",
        )
    return {"ok": True}


@router.get("/documents/{doc_id}/file/with-markups")
async def serve_document_file_with_markups(
    doc_id: int,
    linked_type: str | None = None,
    linked_id: int | None = None,
):
    """Return PDF with current context markups embedded as annotations."""
    if service.get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        pdf_bytes = service.build_pdf_with_markups(
            doc_id, linked_type=linked_type, linked_id=linked_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document file not found")
    doc = service.get_document(doc_id)
    original = doc.get("original_name", doc.get("filename", "document.pdf"))
    base = original.rsplit(".", 1)[0] if "." in original else original
    filename = f"{base}_with_markups.pdf"
    safe = "".join(c for c in filename if ord(c) >= 32 and ord(c) != 127) or "document_with_markups.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@router.post("/documents/{doc_id}/save-pdf")
async def save_document_pdf(doc_id: int, body: SavePdfBody | None = Body(None)):
    """Persist PDF with current context's markups as a new version; previous file kept in versions."""
    if service.get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    linked_type = body.linked_type if body else None
    linked_id = body.linked_id if body else None
    try:
        result = service.save_document_pdf_version(
            doc_id, linked_type=linked_type, linked_id=linked_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document file not found")


@router.post("/documents/{doc_id}/replace")
async def replace_document_file(doc_id: int, file: UploadFile = File(...)):
    """Replace the document file with an uploaded PDF (e.g. flattened PDF with markups baked in)."""
    if service.get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    content_length = file.size if hasattr(file, "size") else None
    if content_length is not None and content_length > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        doc = await asyncio.to_thread(service.replace_document, doc_id, content)
        return {"ok": True, "document": doc}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document file not found")
    except Exception:
        logger.exception("Replace document failed")
        raise HTTPException(status_code=500, detail="Replace failed")
