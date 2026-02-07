"""E2E tests for PDF editor flow. Run with: pytest tests/e2e -v --browser chromium
Requires: pip install pytest-playwright && playwright install chromium"""

import pytest

pytestmark = pytest.mark.e2e

BASE_URL = "http://127.0.0.1:8000"

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


@pytest.fixture
def uploaded_doc(page):
    """Upload a document via API and return doc_id."""
    response = page.request.post(
        f"{BASE_URL}/api/documents/upload",
        multipart={"file": ("test.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert response.ok, f"Upload failed: {response.status}"
    doc = response.json()
    return doc["id"]


def test_open_document_edit_add_highlight(page, uploaded_doc):
    """Open document, Edit, add highlight, Done, verify markups via API."""
    page.goto(f"{BASE_URL}/documents/{uploaded_doc}")
    page.wait_for_load_state("networkidle", timeout=15000)

    edit_btn = page.get_by_role("button", name="Edit")
    edit_btn.click()

    page.wait_for_selector("#edit-mode-only", state="visible", timeout=5000)

    highlight_btn = page.get_by_role("button", name="Highlight")
    highlight_btn.click()

    page.wait_for_selector(".page-annotations", timeout=10000)
    annotation_layer = page.locator(".page-annotations").first
    box = annotation_layer.bounding_box()
    assert box, "Annotation layer not found"
    page.mouse.move(box["x"] + 50, box["y"] + 50)
    page.mouse.down()
    page.mouse.move(box["x"] + 150, box["y"] + 80)
    page.mouse.up()

    page.wait_for_timeout(800)
    done_btn = page.get_by_role("button", name="Done")
    done_btn.click()

    page.wait_for_timeout(1500)

    markups_resp = page.request.get(f"{BASE_URL}/api/documents/{uploaded_doc}/markups")
    assert markups_resp.ok
    data = markups_resp.json()
    assert "markups" in data
    assert len(data["markups"]) >= 1, f"Expected at least 1 markup, got {data}"
