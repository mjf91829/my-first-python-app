"""Unit tests for main PARA API - projects, areas, tasks, archives, resources."""

from fastapi.testclient import TestClient


def test_create_area_project_not_found_returns_404(client: TestClient):
    """Invalid project_id returns 404."""
    response = client.post(
        "/api/areas",
        json={"title": "New Area", "project_id": 99999},
    )
    assert response.status_code == 404


def test_create_task_project_not_found_returns_404(client: TestClient):
    """Invalid parent_id (project) returns 404."""
    response = client.post(
        "/api/tasks",
        json={"title": "Task", "priority": "medium", "parent_type": "project", "parent_id": 99999},
    )
    assert response.status_code == 404


def test_create_task_area_not_found_returns_404(client: TestClient):
    """Invalid parent_id (area) returns 404."""
    response = client.post(
        "/api/tasks",
        json={"title": "Task", "priority": "medium", "parent_type": "area", "parent_id": 99999},
    )
    assert response.status_code == 404


def test_create_task_invalid_parent_type_returns_422(client: TestClient):
    """Invalid parent_type returns 422 from Pydantic."""
    response = client.post(
        "/api/tasks",
        json={"title": "Task", "priority": "medium", "parent_type": "foo", "parent_id": 1},
    )
    assert response.status_code == 422


def test_move_to_archive_project_not_found_returns_404(client: TestClient):
    """Invalid project id returns 404."""
    response = client.post(
        "/api/archives/move",
        json={"type": "project", "id": 99999},
    )
    assert response.status_code == 404


def test_move_to_archive_area_not_found_returns_404(client: TestClient):
    """Invalid area id returns 404."""
    response = client.post(
        "/api/archives/move",
        json={"type": "area", "id": 99999},
    )
    assert response.status_code == 404


def test_move_to_archive_invalid_type_returns_422(client: TestClient):
    """Invalid type returns 422 from Pydantic."""
    response = client.post(
        "/api/archives/move",
        json={"type": "foo", "id": 1},
    )
    assert response.status_code == 422


def test_suggest_when_task_not_found_returns_404(client: TestClient):
    """Missing task returns 404."""
    response = client.get("/api/tasks/99999/suggest")
    assert response.status_code == 404


def test_create_resource_rejects_javascript_url(client: TestClient):
    """javascript: URL returns 422."""
    response = client.post(
        "/api/resources",
        json={"title": "Bad", "url": "javascript:alert(1)", "notes": ""},
    )
    assert response.status_code == 422


def test_create_resource_accepts_https_url(client: TestClient):
    """https:// URL is accepted."""
    response = client.post(
        "/api/resources",
        json={"title": "Good", "url": "https://example.com", "notes": ""},
    )
    assert response.status_code == 200


def test_create_resource_accepts_empty_url(client: TestClient):
    """Empty URL is accepted."""
    response = client.post(
        "/api/resources",
        json={"title": "No URL", "url": "", "notes": ""},
    )
    assert response.status_code == 200


def test_markups_exceeds_max_returns_422(client: TestClient):
    """Markups list > 1000 returns 422."""
    from tests.test_pdf import MINIMAL_PDF

    upload_resp = client.post(
        "/api/documents/upload",
        files={"file": ("m.pdf", MINIMAL_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]
    client.post(f"/api/documents/{doc_id}/link", json={"linked_type": "task", "linked_id": 1})

    markups = [{"id": f"m{i}", "page": 0, "type": "highlight", "bounds": {}} for i in range(1001)]
    response = client.put(
        f"/api/documents/{doc_id}/markups",
        json={"linked_type": "task", "linked_id": 1, "markups": markups},
    )
    assert response.status_code == 422
