"""FastAPI routes for PDF documents."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from pdf_module.models import DocumentLinkCreate, DocumentLinkRemove, MarkupsSaveBody
from pdf_module import service

router = APIRouter(tags=["pdf"])


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        doc = service.upload_document(content, file.filename)
        return doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    return FileResponse(path, media_type="application/pdf", filename=filename)


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
    if linked_type not in ("task", "project", "area"):
        raise HTTPException(status_code=400, detail="linked_type must be task, project, or area")
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
