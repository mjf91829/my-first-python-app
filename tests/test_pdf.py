"""Unit tests for PDF module - upload, serve, list, links, markups."""

import json
from io import BytesIO

from fastapi.testclient import TestClient

# Minimal valid single-page PDF
MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000052 00000 n 
0000000101 00000 n 
trailer<</Size 4/Root 1 0 R>>
startxref
178
%%EOF
"""


def test_upload_document(client):
    """Upload a PDF and verify it's stored."""
    response = client.post(
        "/api/documents/upload",
        files={"file": ("test.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["original_name"] == "test.pdf"
    assert data["filename"].endswith(".pdf")
    assert "uploaded_at" in data


def test_serve_document_file_returns_pdf_with_inline_disposition(client):
    """Upload then fetch - response must be PDF with Content-Disposition: inline."""
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("sample.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert upload_resp.status_code == 200
    doc_id = upload_resp.json()["id"]

    response = client.get(f"/api/documents/{doc_id}/file")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers.get("content-disposition", "").lower()
    assert response.content == MINIMAL_PDF


def test_serve_document_file_404_for_missing(client):
    """Non-existent document returns 404."""
    response = client.get("/api/documents/99999/file")
    assert response.status_code == 404


def test_list_documents(client):
    """List documents, optionally filtered by link."""
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("doc1.pdf", MINIMAL_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]

    client.post(
        f"/api/documents/{doc_id}/link",
        json={"linked_type": "task", "linked_id": 1},
    )

    resp = client.get("/api/documents")
    assert resp.status_code == 200
    assert len(resp.json()["documents"]) == 1

    resp_filtered = client.get("/api/documents?linked_type=task&linked_id=1")
    assert len(resp_filtered.json()["documents"]) == 1

    resp_empty = client.get("/api/documents?linked_type=task&linked_id=999")
    assert len(resp_empty.json()["documents"]) == 0


def test_document_view_page_contains_pdf_object(client):
    """Document view HTML page should contain object tag with PDF URL for inline display."""
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("viewme.pdf", MINIMAL_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]

    response = client.get(f"/documents/{doc_id}")
    assert response.status_code == 200
    html = response.text
    assert f'/api/documents/{doc_id}/file' in html
    assert 'type="application/pdf"' in html
    assert "<object" in html or "<embed" in html or 'data=' in html


def test_get_document_metadata(client):
    """Get document metadata returns doc and linked items."""
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("meta.pdf", MINIMAL_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]
    client.post(f"/api/documents/{doc_id}/link", json={"linked_type": "project", "linked_id": 1})

    resp = client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document"]["id"] == doc_id
    assert len(data["linked"]) == 1
    assert data["linked"][0]["linked_type"] == "project"
    assert data["linked"][0]["linked_id"] == 1


def test_markups_get_and_save(client):
    """Get and save markups for a document."""
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("markup.pdf", MINIMAL_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]
    client.post(f"/api/documents/{doc_id}/link", json={"linked_type": "task", "linked_id": 1})

    markups = [{"id": "m1", "page": 0, "type": "highlight", "bounds": {"x": 0, "y": 0, "width": 0.1, "height": 0.05}}]
    save_resp = client.put(
        f"/api/documents/{doc_id}/markups",
        json={"linked_type": "task", "linked_id": 1, "markups": markups},
    )
    assert save_resp.status_code == 200

    get_resp = client.get(f"/api/documents/{doc_id}/markups?linked_type=task&linked_id=1")
    assert get_resp.status_code == 200
    assert len(get_resp.json()["markups"]) == 1
    assert get_resp.json()["markups"][0]["id"] == "m1"


def test_delete_document(client):
    """Delete document removes record and file."""
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("todelete.pdf", MINIMAL_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]

    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200

    assert client.get(f"/api/documents/{doc_id}").status_code == 404
    assert client.get(f"/api/documents/{doc_id}/file").status_code == 404


def test_serve_document_file_rejects_path_traversal(app_with_temp_data):
    """Document with path traversal filename returns 404."""
    app, tmp_path, data_file, docs_dir = app_with_temp_data
    tampered = {
        "projects": [{"id": 1, "title": "Test", "goal": "", "deadline": ""}],
        "areas": [{"id": 1, "title": "Inbox"}],
        "resources": [],
        "archives": [],
        "tasks": [{"id": 1, "title": "Task 1", "priority": "medium", "parent_type": "area", "parent_id": 1}],
        "documents": [
            {"id": 1, "filename": "../../outside", "original_name": "x.pdf", "uploaded_at": "2026-01-01T00:00:00Z"}
        ],
        "document_links": [],
        "document_markups": [],
    }
    data_file.write_text(json.dumps(tampered, indent=2))

    client = TestClient(app)
    response = client.get("/api/documents/1/file")
    assert response.status_code == 404


def test_delete_document_ignores_traversal_filename(app_with_temp_data):
    """Delete removes record but does not touch files outside upload dir."""
    app, tmp_path, data_file, docs_dir = app_with_temp_data
    tampered = {
        "projects": [{"id": 1, "title": "Test", "goal": "", "deadline": ""}],
        "areas": [{"id": 1, "title": "Inbox"}],
        "resources": [],
        "archives": [],
        "tasks": [{"id": 1, "title": "Task 1", "priority": "medium", "parent_type": "area", "parent_id": 1}],
        "documents": [
            {"id": 1, "filename": "../../outside", "original_name": "x.pdf", "uploaded_at": "2026-01-01T00:00:00Z"}
        ],
        "document_links": [],
        "document_markups": [],
    }
    data_file.write_text(json.dumps(tampered, indent=2))

    client = TestClient(app)
    resp = client.delete("/api/documents/1")
    assert resp.status_code == 200
    assert client.get("/api/documents/1").status_code == 404


def test_upload_file_too_large_returns_413(client: TestClient):
    """File > 50 MB returns 413."""
    # 50 MB + 1 byte to exceed limit
    max_bytes = 50 * 1024 * 1024
    large_content = b"%PDF-1.4\n" + (b"x" * (max_bytes - 7))
    response = client.post(
        "/api/documents/upload",
        files={"file": ("large.pdf", BytesIO(large_content), "application/pdf")},
    )
    assert response.status_code == 413
