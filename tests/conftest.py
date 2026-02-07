"""Shared pytest fixtures for PARA app tests."""

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temp dir with data.json and documents/ for isolated tests."""
    data_file = tmp_path / "data.json"
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()

    default_data = {
        "projects": [{"id": 1, "title": "Test", "goal": "", "deadline": ""}],
        "areas": [{"id": 1, "title": "Inbox"}],
        "resources": [],
        "archives": [],
        "tasks": [{"id": 1, "title": "Task 1", "priority": "medium", "parent_type": "area", "parent_id": 1}],
        "documents": [],
        "document_links": [],
        "document_markups": [],
    }
    data_file.write_text(json.dumps(default_data, indent=2))

    return tmp_path, data_file, docs_dir


@pytest.fixture
def app_with_temp_data(temp_data_dir, monkeypatch):
    """Patch data_access to use temp paths, return app and paths."""
    tmp_path, data_file, docs_dir = temp_data_dir

    monkeypatch.setattr("data_access.DATA_FILE", data_file)
    monkeypatch.setattr("data_access.UPLOAD_DIR", docs_dir)
    monkeypatch.setattr("pdf_module.service.UPLOAD_DIR", docs_dir)

    from main import app
    return app, tmp_path, data_file, docs_dir


@pytest.fixture
def client(app_with_temp_data):
    app, _, _, _ = app_with_temp_data
    return TestClient(app)
