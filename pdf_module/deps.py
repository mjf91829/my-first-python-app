"""FastAPI dependencies for PDF module."""

from fastapi import Depends

from pdf_module.service import PdfService
from repositories import (
    JsonFileMarkupRepository,
    get_document_link_repository,
    get_document_repository,
)


def get_markup_repository(
    doc_repo=Depends(get_document_repository),
    link_repo=Depends(get_document_link_repository),
):
    """Return markup repository with injected doc and link repos."""
    return JsonFileMarkupRepository(doc_repo, link_repo)


def get_pdf_service(
    doc_repo=Depends(get_document_repository),
    link_repo=Depends(get_document_link_repository),
    markup_repo=Depends(get_markup_repository),
) -> PdfService:
    """Return PdfService with injected repositories."""
    return PdfService(doc_repo, link_repo, markup_repo)
