# PDF Markup Save – Data Flow and Bug Hypothesis

## 1. Frontend (JavaScript)

**Save button:** The main save control is the **"Save PDF"** button (`#btn-save-pdf`). There is also **auto-save** 500ms after edits (highlights, comments, etc.).

- **Click handler:** `handleSavePdfClick()` (line ~359) → if dirty or error, calls `performSave(true)`, then `performSavePdf()`.
- **Auto-save:** Any change that affects markups calls `scheduleSave()` (line ~292), which sets `dirty = true` and runs `performSave` after 500ms.

**Data capture:** Markups are kept in a single in-memory array `markups` (line 197). Each entry is an object with at least `id`, `page`, `type` (e.g. `"highlight"`, `"comment"`), `bounds` (coordinates), and optionally `text` for comments. No image blob; it’s structured JSON (coordinates + metadata).

**Save implementation:** `performSave(skipSavePdf)` (lines 298–324):

- Sends **PUT** to `/api/documents/${DOC_ID}/markups`
- Body: `JSON.stringify({ linked_type: currentLinkedType, linked_id: currentLinkedId, markups: markups })`
- On non-ok response it throws, sets `saveStatus = 'error'`, and shows “Failed to save · Retry”.

So the **sending stage (JS)** is correct: it sends the current context and the full `markups` array.

---

## 2. API (FastAPI)

**Endpoint:** `PUT /api/documents/{doc_id}/markups` (in `pdf_module/routes.py`, lines 123–147).

- Handler: `save_document_markups(doc_id, body: MarkupsSaveBody)`.
- Body model: `MarkupsSaveBody`: `linked_type: str | None`, `linked_id: int | None`, `markups: list[dict]`.
- It calls `service.set_markups(doc_id, body.markups, linked_type=body.linked_type, linked_id=body.linked_id)`.
- If `set_markups` returns **False**, the handler raises **HTTP 400** with:  
  `"Invalid context or (linked_type, linked_id) not linked to this document"`.
- If it returns True, the handler returns `{"ok": True}` (200).

So the **receiving stage (API)** is where the request can be **rejected with 400** when the context is invalid.

---

## 3. Backend (Python – persistence)

**Service:** `pdf_module/service.py` – `set_markups()` (lines 199–240).

- Loads data with `load_data()` (from `data_access`), validates document exists and context rules:
  - Either both `linked_type` and `linked_id` are **None** (document-level markups), or both are set.
  - If both are set, they must be `"task"` / `"project"` / `"area"` and the document must appear in `document_links` for that `(linked_type, linked_id)`.
- If validation fails, returns **False** (API turns this into 400).
- If it passes: updates `data["document_markups"]` (replaces the record for that `(doc_id, linked_type, linked_id)`), then calls **`save_data(data)`**.

**Persistence:** `data_access.save_data()` (lines 89–92) takes the updated dict and writes it to `data.json` (via a lock and a `.tmp` + replace). So when `set_markups` returns True, the **writing stage** does persist to the file system.

---

## 4. Hypothesis: Where the connection is broken

**Conclusion: the connection is broken at the receiving stage (API), not at sending or writing.**

- **Sending (JS):** Payload and URL are correct; markups and context are sent as JSON.
- **Writing (Python):** When `set_markups` returns True, `save_data(data)` is called and `data.json` is updated.
- **Receiving (API):** The only way the client can get a “success” UI (e.g. “All changes saved”) is if the API returns 200. If the API returns **400**, the frontend shows “Failed to save · Retry” and does not clear `dirty`. So if the user says “Save doesn’t persist” and they are not seeing that error, either:
  1. They didn’t notice the error indicator, or  
  2. There is another path (e.g. a different “Save” control or a race).

The most likely cause is **validation in `set_markups` failing** and the API returning **400**:

- The page can load with `linked_type` and `linked_id` from the URL (e.g. from a project/task view). Those values are copied into `currentLinkedType` and `currentLinkedId`.
- When the context dropdown is built from `linkedOptions`, it only contains links that **this document** actually has in `document_links`. If the URL context is **not** in that list (e.g. document opened with `?linked_type=project&linked_id=1` but this document is not linked to project 1), the dropdown never gets that option, but the script **does not** clear `currentLinkedType` / `currentLinkedId`. So the frontend still sends that context, and the backend correctly rejects it with 400.

So: **the connection is broken at the receiving stage (API)** – the server rejects the save because the (doc_id, linked_type, linked_id) context is invalid (document not linked to that PARA item).

---

## 5. Recommended fix (frontend)

After building the context dropdown from `linkedOptions`, if the page was loaded with a context (`LINKED_TYPE` / `LINKED_ID`) that is **not** in the dropdown (i.e. not in the document’s links), **reset to document-level** so the next save uses `(null, null)` and succeeds:

- In `loadLinkedOptions()`, when `hasContext` is true but `found` is false, set:
  - `currentLinkedType = null`
  - `currentLinkedId = null`
  - and set `contextSelect.value = ''` (Document (no context)).

That way, even when the URL has an invalid context, the first save (and all subsequent saves) will use document-level markups and persist correctly.
