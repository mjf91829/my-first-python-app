# Task Manager

A lightweight web application for managing tasks with priority levels and optional AI-style suggestions for when to do each task.

---

## About

Task Manager is a simple FastAPI-backed web app that lets you create tasks, assign priorities (High, Medium, Low), and store them in a local JSON file. The UI lists all tasks and provides a **"When should I do this?"** button that returns a contextual suggestion based on priority (e.g., do high-priority tasks today, medium this week, low when you have time). The suggestion logic is currently **mocked** and can be replaced later with a real AI or scheduling service.

**Features:**

- Add tasks with a title and priority
- View all tasks on a single page
- Persistent storage via a local `tasks.json` file
- Per-task “When should I do this?” suggestion (mocked)

---

## How to Install

### Prerequisites

- **Python 3.10+**
- `pip` (usually included with Python)

### Steps

1. **Clone or download the repository** and go into the project folder:
   ```bash
   cd path/to/task_app
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

Tasks are stored in `tasks.json` in the project directory (created automatically when you add your first task).

---

## Tech Stack

| Layer        | Technology |
|-------------|------------|
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) |
| **Server**  | [Uvicorn](https://www.uvicorn.org/) (ASGI) |
| **Templates** | [Jinja2](https://jinja.palletsprojects.com/) |
| **Validation** | [Pydantic](https://docs.pydantic.dev/) (included with FastAPI) |
| **Storage** | Local JSON file (`tasks.json`) |

Frontend is plain HTML, CSS, and JavaScript with no separate framework.
