# PARA Task App

A lightweight web application for organizing work using the PARA method: **P**rojects, **A**reas, **R**esources, and **A**rchives, with tasks as children of projects or areas. Includes PDF document upload, viewing, and markup linked to projects, areas, or tasks.

---

## About

PARA Task App is a FastAPI-backed web app that lets you manage projects, areas, resources, and archives; create tasks under projects or areas; and attach PDF documents with highlights and annotations. The UI provides a **"When should I do this?"** suggestion per task (mocked; can be replaced with a real AI or scheduling service).

**Features:**

- **Projects & areas** – Create projects with goals/deadlines and areas (optionally under a project).
- **Tasks** – Add tasks with priority (High, Medium, Low) under a project or area.
- **Resources** – Store links (http/https) and notes.
- **Archives** – Move completed projects or areas to archive (with their tasks).
- **Documents** – Upload PDFs, link them to a project/area/task, view and annotate (highlights, comments, ink).
- **Storage** – Primary store is `data.json`. Optional one-time migration from legacy `tasks.json` (see `archive/` if upgrading from an older task-only install).

---

## How to Install

### Prerequisites

- **Python 3.10+**
- `pip` (usually included with Python)

### Steps

1. **Clone or download the repository** and go into the project folder:
   ```bash
   cd path/to/my-first-python-app
   ```

2. **Create and activate a virtual environment** (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
   On macOS/Linux: `source venv/bin/activate`

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python main.py
   ```
   Or with Uvicorn directly:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Open in a browser:**  
   [http://localhost:8000](http://localhost:8000)

Data is stored in `data.json` in the project directory (created automatically on first use). Uploaded PDFs are stored in the `documents/` folder. Legacy `tasks.json` is only used for a one-time migration when `data.json` does not exist; see `archive/` for archived reference files.

---

## Tech Stack

| Layer        | Technology |
|-------------|------------|
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) |
| **Server**  | [Uvicorn](https://www.uvicorn.org/) (ASGI) |
| **Templates** | [Jinja2](https://jinja.palletsprojects.com/) |
| **Validation** | [Pydantic](https://docs.pydantic.dev/) (included with FastAPI) |
| **Storage** | `data.json` (PARA + documents + document_links + document_markups); optional legacy migration from `tasks.json`; PDF files in `documents/` |

Frontend is plain HTML, CSS, and JavaScript (with PDF.js for document viewing). All programmatic APIs live under `/api`.
