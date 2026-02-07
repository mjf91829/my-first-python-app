"""Unit tests for data_access module."""

import json

from data_access import default_data, load_data, next_id, save_data


def test_load_data_returns_default_when_file_missing(tmp_path, monkeypatch):
    """No data file → default_data()."""
    monkeypatch.setattr("data_access.DATA_FILE", tmp_path / "nonexistent.json")
    monkeypatch.setattr("data_access.TASKS_FILE_LEGACY", tmp_path / "tasks.json")
    (tmp_path / "tasks.json").write_text("[]")  # empty legacy, won't trigger migration
    data = load_data()
    assert data == default_data()


def test_load_data_returns_parsed_data_when_file_exists(tmp_path, monkeypatch):
    """Valid JSON → correct structure."""
    monkeypatch.setattr("data_access.DATA_FILE", tmp_path / "data.json")
    monkeypatch.setattr("data_access.TASKS_FILE_LEGACY", tmp_path / "tasks.json")
    expected = {"projects": [{"id": 1, "title": "P"}], "areas": [], "resources": [], "archives": [], "tasks": [], "documents": [], "document_links": [], "document_markups": []}
    (tmp_path / "data.json").write_text(json.dumps(expected, indent=2))
    data = load_data()
    assert data["projects"] == [{"id": 1, "title": "P"}]
    assert "documents" in data
    assert "document_links" in data
    assert "document_markups" in data


def test_load_data_handles_corrupt_json(tmp_path, monkeypatch):
    """Invalid JSON → default_data() and no crash."""
    monkeypatch.setattr("data_access.DATA_FILE", tmp_path / "data.json")
    monkeypatch.setattr("data_access.TASKS_FILE_LEGACY", tmp_path / "tasks.json")
    (tmp_path / "data.json").write_text("{ invalid json")
    data = load_data()
    assert data == default_data()


def test_save_data_atomic(tmp_path, monkeypatch):
    """Save writes to .tmp and atomically replaces; no partial file on success."""
    monkeypatch.setattr("data_access.DATA_FILE", tmp_path / "data.json")
    monkeypatch.setattr("data_access.TASKS_FILE_LEGACY", tmp_path / "tasks.json")
    data = {"projects": [], "areas": [], "resources": [], "archives": [], "tasks": [], "documents": [], "document_links": [], "document_markups": []}
    save_data(data)
    assert (tmp_path / "data.json").exists()
    assert not (tmp_path / "data.tmp").exists()
    loaded = json.loads((tmp_path / "data.json").read_text())
    assert loaded == data


def test_next_id_empty_returns_1():
    """Empty list → 1."""
    data = {"projects": []}
    assert next_id("projects", data) == 1


def test_next_id_normal():
    """[{"id": 3}] → 4."""
    data = {"projects": [{"id": 3, "title": "P"}]}
    assert next_id("projects", data) == 4


def test_next_id_skips_malformed_items():
    """Mixed valid, empty, non-int, non-dict → next valid id."""
    data = {
        "projects": [
            {"id": 5, "title": "P1"},
            {},
            {"id": "x", "title": "P2"},
            {"id": 3, "title": "P3"},
            "not a dict",
        ]
    }
    assert next_id("projects", data) == 6


def test_load_and_save_roundtrip(tmp_path, monkeypatch):
    """Save then load → data unchanged."""
    monkeypatch.setattr("data_access.DATA_FILE", tmp_path / "data.json")
    monkeypatch.setattr("data_access.TASKS_FILE_LEGACY", tmp_path / "tasks.json")
    original = {
        "projects": [{"id": 1, "title": "A"}],
        "areas": [{"id": 2, "title": "B"}],
        "resources": [],
        "archives": [],
        "tasks": [],
        "documents": [],
        "document_links": [],
        "document_markups": [],
    }
    save_data(original)
    loaded = load_data()
    assert loaded["projects"] == original["projects"]
    assert loaded["areas"] == original["areas"]
