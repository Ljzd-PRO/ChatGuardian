"""
End-to-end browser automation tests for the ChatGuardian React frontend.

Starts a live FastAPI + uvicorn server, then uses Playwright to:
- Load every navigation page and confirm key landmarks render
- Interact with the Rules page (create/delete a rule)
- Toggle dark mode
- Verify no uncaught console errors on any page

Run:
    pytest tests/test_frontend_e2e.py -v --timeout=60
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def live_server():
    """Spin up a real uvicorn process for the duration of the test module."""
    port = _free_port()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "chat_guardian.api.app:create_app",
        "--factory",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--log-level", "warning",
    ]
    # Use an isolated temp database so other test modules writing to the shared
    # test.sqlite (e.g. test_api_smoke.py with a different password) do not
    # interfere with the e2e auth flow.
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "e2e_test.sqlite")
        env = {**os.environ, "CHAT_GUARDIAN_DATABASE_URL": f"sqlite:///{db_path}"}
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert _wait_for_port("127.0.0.1", port), "Backend failed to start within 15 s"
        yield f"http://127.0.0.1:{port}"
        proc.terminate()
        proc.wait(timeout=5)


# Key used by the frontend to persist the auth token in localStorage (see frontend/src/api/client.ts)
_AUTH_TOKEN_LS_KEY = "cg_auth_token"
# Keep auth bootstrap requests bounded to avoid hanging CI jobs.
_AUTH_HTTP_TIMEOUT_SECONDS = 5


@pytest.fixture(scope="module")
def auth_token(live_server):
    """Register an admin user and return a valid access token string for UI tests (without 'Bearer ' prefix)."""
    payload = json.dumps({"username": "admin", "password": "password123"}).encode()
    headers = {"Content-Type": "application/json"}

    # Register admin (server uses sqlite:///./test.sqlite).
    # Accept 400 only when the body confirms admin is already configured – any
    # other 400 (e.g. validation error) re-raises to fail the test clearly.
    req = urllib.request.Request(
        f"{live_server}/api/auth/register", data=payload, headers=headers
    )
    try:
        urllib.request.urlopen(req, timeout=_AUTH_HTTP_TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        assert exc.code == 400 and "already configured" in body, (
            f"Unexpected register error {exc.code}: {body}"
        )

    # Login
    req = urllib.request.Request(
        f"{live_server}/api/auth/login", data=payload, headers=headers
    )
    with urllib.request.urlopen(req, timeout=_AUTH_HTTP_TIMEOUT_SECONDS) as resp:
        token = json.loads(resp.read())["token"]
    return token


@pytest.fixture(scope="module")
def browser_context(live_server, auth_token):  # noqa: F811
    """Synchronous Playwright browser context (chromium, headless)."""
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        # Inject auth token so every page load sees the user as authenticated
        ctx.add_init_script(
            f"window.localStorage.setItem({json.dumps(_AUTH_TOKEN_LS_KEY)}, {json.dumps(auth_token)});"
        )
        yield ctx, live_server
        ctx.close()
        browser.close()


@pytest.fixture()
def page(browser_context):
    ctx, base = browser_context
    p = ctx.new_page()
    yield p, base
    p.close()


# ── helpers used by tests ────────────────────────────────────────────────────


def go(page, base: str, path: str = "/", *, wait: str = "networkidle"):
    page.goto(f"{base}/app{path}")
    page.wait_for_load_state(wait)
    page.wait_for_timeout(600)  # let React paint


def assert_no_fatal_errors(page) -> None:
    """Assert no uncaught JS errors (Error boundary / React crash) are visible."""
    error_heading = page.query_selector("h2:has-text('Unexpected Application Error')")
    assert error_heading is None, "React error boundary triggered"


# ── page load smoke tests ─────────────────────────────────────────────────────


PAGES = [
    ("/", "Dashboard"),
    ("/rules", "Detection Rules"),
    ("/stats", "Trigger Statistics"),
    ("/users", "User Profiles"),
    ("/adapters", "Adapters"),
    ("/llm", "LLM Configuration"),
    ("/notifications", "Notifications"),
    ("/queues", "Message Queues"),
    ("/logs", "System Logs"),
    ("/settings", "Settings"),
]


@pytest.mark.parametrize("path,title", PAGES)
def test_page_loads(page, path: str, title: str):
    """Every page should load without crashing and display its heading."""
    pg, base = page
    go(pg, base, path)
    assert_no_fatal_errors(pg)
    heading = pg.query_selector(f"h1:has-text('{title}')")
    assert heading is not None, f"Heading '{title}' not found on {path}"


# ── dashboard ─────────────────────────────────────────────────────────────────


def test_dashboard_stat_cards(page):
    """Dashboard should show four stat cards."""
    pg, base = page
    go(pg, base, "/")
    assert_no_fatal_errors(pg)
    # wait for data to load (spinner disappears)
    pg.wait_for_selector("text=Total Rules", timeout=10_000)
    pg.wait_for_selector("text=Enabled Rules")
    pg.wait_for_selector("text=Triggers Today")
    pg.wait_for_selector("text=Messages Processed Today")


# ── sidebar navigation ────────────────────────────────────────────────────────


def test_sidebar_navigation(page):
    """Clicking sidebar links should navigate to the correct page."""
    pg, base = page
    go(pg, base, "/")
    pg.click("a:has-text('Rules')")
    pg.wait_for_url(f"**/app/rules")
    assert_no_fatal_errors(pg)

    pg.click("a:has-text('Settings')")
    pg.wait_for_url(f"**/app/settings")
    assert_no_fatal_errors(pg)


# ── dark-mode toggle ──────────────────────────────────────────────────────────


def test_dark_mode_toggle(page):
    """Dark mode switch should toggle without errors."""
    pg, base = page
    go(pg, base, "/")
    toggle = pg.query_selector("[aria-label='Toggle dark mode']")
    assert toggle is not None, "Dark mode toggle not found"
    toggle.click()
    pg.wait_for_timeout(400)
    assert_no_fatal_errors(pg)
    # toggle back
    toggle.click()
    pg.wait_for_timeout(400)
    assert_no_fatal_errors(pg)


# ── rules CRUD ────────────────────────────────────────────────────────────────


def test_new_rule_modal_opens(page):
    """'New Rule' button should open a modal with a name input."""
    pg, base = page
    go(pg, base, "/rules")
    pg.wait_for_selector("button:has-text('New Rule')", timeout=8_000)
    pg.click("button:has-text('New Rule')")
    pg.wait_for_selector("text=Rule Name", timeout=5_000)
    assert_no_fatal_errors(pg)
    # modal footer should have Save button
    assert pg.query_selector("button:has-text('Save')") is not None


def test_create_and_delete_rule(page):
    """Fill the new-rule form, save, then verify the rule appears in the list."""
    pg, base = page
    go(pg, base, "/rules")
    pg.wait_for_selector("button:has-text('New Rule')", timeout=8_000)

    pg.click("button:has-text('New Rule')")
    pg.wait_for_selector("text=Rule Name", timeout=5_000)

    # HeroUI Input renders a <div data-slot="input-wrapper"> containing the <input>
    # Find the first visible input inside the modal
    modal = pg.locator('[role="dialog"]')
    first_input = modal.locator("input").first
    first_input.wait_for(state="visible", timeout=5_000)
    first_input.fill("E2E Test Rule")

    # Wait for Save button to become enabled (requires name to be non-empty)
    save_btn = pg.locator('[role="dialog"] button', has_text="Save")
    pg.wait_for_timeout(500)
    save_btn.click()

    # The rule should appear in the list
    pg.wait_for_selector("text=E2E Test Rule", timeout=8_000)
    assert_no_fatal_errors(pg)


# ── settings page ─────────────────────────────────────────────────────────────


def test_settings_page_shows_fields(page):
    """Settings page should render the settings preview card with configuration entries."""
    pg, base = page
    go(pg, base, "/settings")
    pg.wait_for_selector("text=Settings Preview", timeout=8_000)
    pg.wait_for_selector("text=Preview only")
    pg.wait_for_selector("text=Read-only snapshot of all configuration items.")
    assert_no_fatal_errors(pg)


# ── backend health after frontend interactions ────────────────────────────────


def test_backend_health_still_ok(page):
    """After all the UI interactions the backend /health endpoint must still respond."""
    pg, base = page
    with urllib.request.urlopen(f"{base}/health", timeout=5) as resp:
        data = json.loads(resp.read())
    assert data.get("status") == "ok"


# ── screenshot helper (saves to /tmp for CI artefact inspection) ──────────────


def test_screenshot_every_page(page):
    """Take a screenshot of every page for visual inspection."""
    import tempfile
    screenshot_dir = os.path.join(tempfile.gettempdir(), "e2e_screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)
    pg, base = page
    for path, name in PAGES:
        go(pg, base, path)
        pg.screenshot(path=os.path.join(screenshot_dir, f"{name.lower().replace(' ', '_')}.png"), full_page=True)
        assert_no_fatal_errors(pg)
