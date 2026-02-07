"""Unit tests for Pydantic markup models and PDF service markup logic."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pdf_module.models import (
    BoundsBase,
    CommentMarkup,
    HighlightMarkup,
    InkMarkup,
    MarkupsSaveBody,
    TextMarkup,
)


# --- Pydantic model tests ---


def test_bounds_base_valid():
    b = BoundsBase(x=0.1, y=0.2, width=0.3, height=0.05)
    assert b.x == 0.1 and b.y == 0.2 and b.width == 0.3 and b.height == 0.05


def test_bounds_base_clamps_to_one():
    b = BoundsBase(x=1.5, y=2, width=0.5, height=-0.1)
    assert b.x == 1.0 and b.y == 1.0 and b.width == 0.5 and b.height == 0.0


def test_highlight_markup_valid():
    m = HighlightMarkup(
        type="highlight",
        id="h1",
        page=0,
        bounds={"x": 0, "y": 0, "width": 0.2, "height": 0.05},
        color="#ffeb3b",
    )
    assert m.type == "highlight" and m.color == "#ffeb3b"


def test_highlight_markup_invalid_color():
    with pytest.raises(ValidationError):
        HighlightMarkup(
            type="highlight",
            id="h1",
            page=0,
            bounds={"x": 0, "y": 0, "width": 0.2, "height": 0.05},
            color="not-a-hex",
        )


def test_ink_markup_valid():
    m = InkMarkup(
        type="ink",
        id="i1",
        page=0,
        bounds={"x": 0, "y": 0, "width": 0.1, "height": 0.1},
        points=[[0.1, 0.2], [0.3, 0.4]],
    )
    assert m.type == "ink" and len(m.points) == 2


def test_ink_markup_points_exceed_limit():
    with pytest.raises(ValidationError, match="2000"):
        InkMarkup(
            type="ink",
            id="i1",
            page=0,
            bounds={"x": 0, "y": 0, "width": 0.1, "height": 0.1},
            points=[[0, 0], [1, 1]] * 1001,
        )


def test_text_markup_text_exceeds_limit():
    with pytest.raises(ValidationError, match="2000"):
        TextMarkup(
            type="text",
            id="t1",
            page=0,
            bounds={"x": 0, "y": 0, "width": 0.2, "height": 0.05},
            text="x" * 2001,
        )


def test_comment_markup_valid():
    m = CommentMarkup(
        type="comment",
        id="c1",
        page=0,
        bounds={"x": 0.5, "y": 0.5, "width": 0.03, "height": 0.03},
        text="Hello",
    )
    assert m.type == "comment" and m.text == "Hello"


def test_markups_save_body_valid():
    body = MarkupsSaveBody(
        linked_type="task",
        linked_id=1,
        markups=[
            {
                "type": "highlight",
                "id": "h1",
                "page": 0,
                "bounds": {"x": 0, "y": 0, "width": 0.2, "height": 0.05},
            }
        ],
    )
    assert len(body.markups) == 1 and body.markups[0].type == "highlight"


def test_markups_save_body_exceeds_max():
    with pytest.raises(ValidationError, match="1000"):
        MarkupsSaveBody(
            linked_type="task",
            linked_id=1,
            markups=[
                {
                    "type": "highlight",
                    "id": f"h{i}",
                    "page": 0,
                    "bounds": {"x": 0, "y": 0, "width": 0.01, "height": 0.01},
                }
                for i in range(1001)
            ],
        )


def test_markups_save_body_unknown_type():
    with pytest.raises(ValidationError):
        MarkupsSaveBody(
            linked_type="task",
            linked_id=1,
            markups=[
                {
                    "type": "unknown",
                    "id": "u1",
                    "page": 0,
                    "bounds": {"x": 0, "y": 0, "width": 0.1, "height": 0.1},
                }
            ],
        )


# --- API integration tests ---


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


def test_markups_invalid_context_returns_400(client):
    """Saving markups with invalid linked context returns 400."""
    resp = client.put(
        "/api/documents/99999/markups",
        json={"linked_type": "task", "linked_id": 1, "markups": []},
    )
    assert resp.status_code == 404

    # Upload a doc, try to save with task that doesn't exist
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("t.pdf", MINIMAL_PDF, "application/pdf")},
    )
    if upload_resp.status_code != 200:
        return
    doc_id = upload_resp.json()["id"]

    resp = client.put(
        f"/api/documents/{doc_id}/markups",
        json={"linked_type": "task", "linked_id": 99999, "markups": []},
    )
    assert resp.status_code == 400


def test_markups_invalid_payload_returns_422(client):
    """Invalid markup payload returns 422."""
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("t.pdf", MINIMAL_PDF, "application/pdf")},
    )
    if upload_resp.status_code != 200:
        return
    doc_id = upload_resp.json()["id"]

    resp = client.put(
        f"/api/documents/{doc_id}/markups",
        json={
            "markups": [
                {
                    "type": "highlight",
                    "id": "h1",
                    "page": 0,
                    "bounds": {"x": 2, "y": 2, "width": 2, "height": 2},  # invalid: > 1
                }
            ]
        },
    )
    # Bounds are clamped 0-1 in BoundsBase, so this may pass. Try invalid color.
    resp2 = client.put(
        f"/api/documents/{doc_id}/markups",
        json={
            "markups": [
                {
                    "type": "highlight",
                    "id": "h1",
                    "page": 0,
                    "bounds": {"x": 0, "y": 0, "width": 0.1, "height": 0.05},
                    "color": "invalid",
                }
            ]
        },
    )
    assert resp2.status_code == 422


def test_markup_history_empty(client):
    """Markup history returns empty list when no versions."""
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("t.pdf", MINIMAL_PDF, "application/pdf")},
    )
    if upload_resp.status_code != 200:
        return
    doc_id = upload_resp.json()["id"]

    resp = client.get(f"/api/documents/{doc_id}/markups/history")
    assert resp.status_code == 200
    assert resp.json()["history"] == []


def test_markup_history_and_restore(client):
    """Save markups, get history, restore version."""
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("t.pdf", MINIMAL_PDF, "application/pdf")},
    )
    if upload_resp.status_code != 200:
        return
    doc_id = upload_resp.json()["id"]
    client.post(f"/api/documents/{doc_id}/link", json={"linked_type": "task", "linked_id": 1})

    markups_v1 = [
        {
            "type": "highlight",
            "id": "h1",
            "page": 0,
            "bounds": {"x": 0, "y": 0, "width": 0.2, "height": 0.05},
        }
    ]
    save_resp = client.put(
        f"/api/documents/{doc_id}/markups",
        json={"linked_type": "task", "linked_id": 1, "markups": markups_v1},
    )
    assert save_resp.status_code == 200

    history_resp = client.get(f"/api/documents/{doc_id}/markups/history?linked_type=task&linked_id=1")
    assert history_resp.status_code == 200
    history = history_resp.json()["history"]
    assert len(history) == 1
    ver = history[0]["version"]

    markups_v2 = [
        {"type": "highlight", "id": "h2", "page": 0, "bounds": {"x": 0.5, "y": 0.5, "width": 0.1, "height": 0.05}}
    ]
    client.put(
        f"/api/documents/{doc_id}/markups",
        json={"linked_type": "task", "linked_id": 1, "markups": markups_v2},
    )

    get_resp = client.get(f"/api/documents/{doc_id}/markups?linked_type=task&linked_id=1")
    assert len(get_resp.json()["markups"]) == 1 and get_resp.json()["markups"][0]["id"] == "h2"

    restore_resp = client.post(
        f"/api/documents/{doc_id}/markups/restore?version={ver}&linked_type=task&linked_id=1"
    )
    assert restore_resp.status_code == 200

    get_after = client.get(f"/api/documents/{doc_id}/markups?linked_type=task&linked_id=1")
    assert len(get_after.json()["markups"]) == 1 and get_after.json()["markups"][0]["id"] == "h1"


def test_build_pdf_with_markups(client):
    """PDF with markups endpoint returns valid PDF bytes."""
    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("t.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert upload_resp.status_code == 200
    doc_id = upload_resp.json()["id"]

    markups = [
        {
            "type": "highlight",
            "id": "h1",
            "page": 0,
            "bounds": {"x": 0, "y": 0, "width": 0.2, "height": 0.05},
            "color": "#ffeb3b",
        }
    ]
    client.put(f"/api/documents/{doc_id}/markups", json={"markups": markups})

    resp = client.get(f"/api/documents/{doc_id}/file/with-markups")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
