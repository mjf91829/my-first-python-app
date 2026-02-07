"""E2E test fixtures - requires app running at http://127.0.0.1:8000."""

import subprocess
import time

import pytest


@pytest.fixture(scope="session")
def app_server():
    """Start uvicorn server for E2E tests if not already running."""
    import urllib.request

    try:
        urllib.request.urlopen("http://127.0.0.1:8000/", timeout=1)
        yield
        return
    except Exception:
        pass

    proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=".",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    try:
        yield
    finally:
        proc.terminate()
        proc.wait(timeout=5)


@pytest.fixture
def page_with_base(page, app_server):
    """Page fixture with base URL set."""
    page.set_default_navigation_timeout(15000)
    page.set_default_timeout(10000)
    return page
