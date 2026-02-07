"""Repository interfaces and JSON-file implementations for PDF module storage."""

from datetime import datetime, timezone
from typing import Protocol

from constants import AREA, PROJECT, TASK
from data_access import load_data, next_id, save_data

MAX_MARKUP_VERSIONS = 20


def _markup_record_key(rec: dict) -> tuple[int | None, str | None, int | None]:
    """(document_id, linked_type, linked_id) for matching. None means document-level."""
    return (
        rec.get("document_id"),
        rec.get("linked_type"),
        rec.get("linked_id"),
    )


class DocumentRepository(Protocol):
    """Interface for document metadata storage."""

    def get(self, doc_id: int) -> dict | None:
        """Get document by id."""
        ...

    def list_all(self) -> list[dict]:
        """List all documents."""
        ...

    def list_by_link(self, linked_type: str, linked_id: int) -> list[dict]:
        """List documents linked to a PARA item."""
        ...

    def next_id(self) -> int:
        """Return next document id."""
        ...

    def add(self, doc: dict) -> None:
        """Add a document."""
        ...

    def update_filename(self, doc_id: int, filename: str) -> None:
        """Update document filename and append old to versions."""
        ...

    def delete(self, doc_id: int) -> bool:
        """Delete document and its links/markups. Returns True if deleted."""
        ...


class DocumentLinkRepository(Protocol):
    """Interface for document-PARA link storage."""

    def get_links(self, doc_id: int) -> list[dict]:
        """Get all links for a document."""
        ...

    def add_link(self, doc_id: int, linked_type: str, linked_id: int) -> bool:
        """Add link. Returns False if doc/PARA item invalid or already linked."""
        ...

    def remove_link(self, doc_id: int, linked_type: str, linked_id: int) -> bool:
        """Remove link. Returns True if removed."""
        ...

    def get_doc_ids_for_para(self, linked_type: str, linked_id: int) -> set[int]:
        """Get document ids linked to a PARA item."""
        ...

    def is_linked(self, doc_id: int, linked_type: str, linked_id: int) -> bool:
        """Check if document is linked to PARA item."""
        ...


class MarkupRepository(Protocol):
    """Interface for document markup storage."""

    def get_markups(
        self,
        doc_id: int,
        linked_type: str | None = None,
        linked_id: int | None = None,
    ) -> list[dict]:
        """Get markups for document and context."""
        ...

    def set_markups(
        self,
        doc_id: int,
        markups: list[dict],
        linked_type: str | None = None,
        linked_id: int | None = None,
    ) -> bool:
        """Save markups. Returns False if validation fails."""
        ...

    def validate_context(
        self,
        doc_id: int,
        linked_type: str | None,
        linked_id: int | None,
    ) -> bool:
        """Check document exists and context is valid."""
        ...

    def get_history(
        self,
        doc_id: int,
        linked_type: str | None = None,
        linked_id: int | None = None,
    ) -> list[dict]:
        """Get markup version history: [{ version, created_at }, ...]."""
        ...

    def restore_version(
        self,
        doc_id: int,
        version: int,
        linked_type: str | None = None,
        linked_id: int | None = None,
    ) -> bool:
        """Restore markups from version. Returns False if version not found."""
        ...


# --- JSON file implementations ---


class JsonFileDocumentRepository:
    """Document storage backed by data.json."""

    def get(self, doc_id: int) -> dict | None:
        data = load_data()
        return next((d for d in data.get("documents", []) if d["id"] == doc_id), None)

    def list_all(self) -> list[dict]:
        data = load_data()
        return list(data.get("documents", []))

    def list_by_link(self, linked_type: str, linked_id: int) -> list[dict]:
        data = load_data()
        links = data.get("document_links", [])
        doc_ids = {
            lnk["document_id"]
            for lnk in links
            if lnk.get("linked_type") == linked_type and lnk.get("linked_id") == linked_id
        }
        return [d for d in data.get("documents", []) if d["id"] in doc_ids]

    def next_id(self) -> int:
        data = load_data()
        return next_id("documents", data)

    def add(self, doc: dict) -> None:
        data = load_data()
        data.setdefault("documents", []).append(doc)
        save_data(data)

    def update_filename(self, doc_id: int, filename: str) -> None:
        data = load_data()
        doc_ref = next((d for d in data["documents"] if d["id"] == doc_id), None)
        if not doc_ref:
            return
        doc_ref.setdefault("versions", []).append(doc_ref["filename"])
        doc_ref["filename"] = filename
        save_data(data)

    def delete(self, doc_id: int) -> bool:
        data = load_data()
        doc = next((d for d in data["documents"] if d["id"] == doc_id), None)
        if not doc:
            return False
        data["documents"] = [d for d in data["documents"] if d["id"] != doc_id]
        data["document_links"] = [
            lnk for lnk in data.get("document_links", []) if lnk.get("document_id") != doc_id
        ]
        data["document_markups"] = [
            m for m in data.get("document_markups", []) if m.get("document_id") != doc_id
        ]
        save_data(data)
        return True


class JsonFileDocumentLinkRepository:
    """Document link storage backed by data.json."""

    def get_links(self, doc_id: int) -> list[dict]:
        data = load_data()
        return [lnk for lnk in data.get("document_links", []) if lnk.get("document_id") == doc_id]

    def add_link(self, doc_id: int, linked_type: str, linked_id: int) -> bool:
        if linked_type not in (TASK, PROJECT, AREA):
            return False
        data = load_data()
        if not any(d["id"] == doc_id for d in data.get("documents", [])):
            return False
        if linked_type == PROJECT and not any(p["id"] == linked_id for p in data.get("projects", [])):
            return False
        if linked_type == AREA and not any(a["id"] == linked_id for a in data.get("areas", [])):
            return False
        if linked_type == TASK and not any(t["id"] == linked_id for t in data.get("tasks", [])):
            return False
        if any(
            lnk.get("document_id") == doc_id
            and lnk.get("linked_type") == linked_type
            and lnk.get("linked_id") == linked_id
            for lnk in data.get("document_links", [])
        ):
            return True  # already linked
        data.setdefault("document_links", []).append(
            {"document_id": doc_id, "linked_type": linked_type, "linked_id": linked_id}
        )
        save_data(data)
        return True

    def remove_link(self, doc_id: int, linked_type: str, linked_id: int) -> bool:
        data = load_data()
        before = len(data.get("document_links", []))
        data["document_links"] = [
            lnk
            for lnk in data.get("document_links", [])
            if not (
                lnk.get("document_id") == doc_id
                and lnk.get("linked_type") == linked_type
                and lnk.get("linked_id") == linked_id
            )
        ]
        if len(data["document_links"]) < before:
            save_data(data)
            return True
        return False

    def get_doc_ids_for_para(self, linked_type: str, linked_id: int) -> set[int]:
        data = load_data()
        return {
            lnk["document_id"]
            for lnk in data.get("document_links", [])
            if lnk.get("linked_type") == linked_type and lnk.get("linked_id") == linked_id
        }

    def is_linked(self, doc_id: int, linked_type: str, linked_id: int) -> bool:
        data = load_data()
        return any(
            lnk.get("document_id") == doc_id
            and lnk.get("linked_type") == linked_type
            and lnk.get("linked_id") == linked_id
            for lnk in data.get("document_links", [])
        )


class JsonFileMarkupRepository:
    """Markup storage backed by data.json."""

    def __init__(self, doc_repo: DocumentRepository, link_repo: DocumentLinkRepository):
        self._doc_repo = doc_repo
        self._link_repo = link_repo

    def get_markups(
        self,
        doc_id: int,
        linked_type: str | None = None,
        linked_id: int | None = None,
    ) -> list[dict]:
        if not self._doc_repo.get(doc_id):
            return []
        data = load_data()
        records = data.get("document_markups", [])
        for rec in records:
            if _markup_record_key(rec) == (doc_id, linked_type, linked_id):
                return list(rec.get("markups", []))
        return []

    def set_markups(
        self,
        doc_id: int,
        markups: list[dict],
        linked_type: str | None = None,
        linked_id: int | None = None,
    ) -> bool:
        if not self.validate_context(doc_id, linked_type, linked_id):
            return False
        data = load_data()
        records = list(data.get("document_markups", []))
        key = (doc_id, linked_type, linked_id)
        new_rec = {
            "document_id": doc_id,
            "linked_type": linked_type,
            "linked_id": linked_id,
            "markups": markups,
        }
        records = [r for r in records if _markup_record_key(r) != key]
        records.append(new_rec)
        data["document_markups"] = records

        versions = list(data.get("document_markup_versions", []))
        next_ver = 1
        context_versions = [
            v
            for v in versions
            if (
                v.get("document_id") == doc_id
                and v.get("linked_type") == linked_type
                and v.get("linked_id") == linked_id
            )
        ]
        if context_versions:
            next_ver = max(int(v.get("version", 0)) for v in context_versions) + 1
        versions.append({
            "document_id": doc_id,
            "linked_type": linked_type,
            "linked_id": linked_id,
            "version": next_ver,
            "markups": [dict(m) for m in markups],
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        })
        versions = [
            v
            for v in versions
            if not (
                v.get("document_id") == doc_id
                and v.get("linked_type") == linked_type
                and v.get("linked_id") == linked_id
                and int(v.get("version", 0)) <= next_ver - MAX_MARKUP_VERSIONS
            )
        ]
        data["document_markup_versions"] = versions
        save_data(data)
        return True

    def get_history(
        self,
        doc_id: int,
        linked_type: str | None = None,
        linked_id: int | None = None,
    ) -> list[dict]:
        if not self.validate_context(doc_id, linked_type, linked_id):
            return []
        data = load_data()
        versions = [
            {"version": int(v.get("version", 0)), "created_at": v.get("created_at", "")}
            for v in data.get("document_markup_versions", [])
            if (
                v.get("document_id") == doc_id
                and v.get("linked_type") == linked_type
                and v.get("linked_id") == linked_id
            )
        ]
        versions.sort(key=lambda x: x["version"], reverse=True)
        return versions

    def restore_version(
        self,
        doc_id: int,
        version: int,
        linked_type: str | None = None,
        linked_id: int | None = None,
    ) -> bool:
        if not self.validate_context(doc_id, linked_type, linked_id):
            return False
        data = load_data()
        for v in data.get("document_markup_versions", []):
            if (
                v.get("document_id") == doc_id
                and v.get("linked_type") == linked_type
                and v.get("linked_id") == linked_id
                and int(v.get("version", 0)) == version
            ):
                return self.set_markups(
                    doc_id,
                    list(v.get("markups", [])),
                    linked_type=linked_type,
                    linked_id=linked_id,
                )
        return False

    def validate_context(
        self,
        doc_id: int,
        linked_type: str | None,
        linked_id: int | None,
    ) -> bool:
        if not self._doc_repo.get(doc_id):
            return False
        if (linked_type is None) != (linked_id is None):
            return False
        if linked_type is not None and linked_id is not None:
            if linked_type not in (TASK, PROJECT, AREA):
                return False
            if not self._link_repo.is_linked(doc_id, linked_type, linked_id):
                return False
        return True


# --- Dependency / factory ---


def get_document_repository() -> DocumentRepository:
    """Return the document repository instance."""
    return JsonFileDocumentRepository()


def get_document_link_repository() -> DocumentLinkRepository:
    """Return the document link repository instance."""
    return JsonFileDocumentLinkRepository()


def get_markup_repository(
    doc_repo: DocumentRepository,
    link_repo: DocumentLinkRepository,
) -> MarkupRepository:
    """Return the markup repository instance (depends on doc and link repos)."""
    return JsonFileMarkupRepository(doc_repo, link_repo)
