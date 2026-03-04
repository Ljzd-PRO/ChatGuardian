"""
浏览器自动化测试：验证前端 React/Ant Design UI 功能与后端集成。

测试流程：
1. 启动 FastAPI 后端服务（内嵌 fixture）
2. 通过 Playwright 浏览器自动化访问每个页面
3. 验证页面正常加载、各关键组件存在
4. 执行前端交互（创建规则、编辑 Matcher 等）
5. 验证后端接口无报错
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest
import requests

FRONTEND_BASE = "http://127.0.0.1:8765/app"
API_BASE = "http://127.0.0.1:8765"

# ---------------------------------------------------------------------------
# Fixture: start/stop the FastAPI server for the duration of the test session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def start_backend_server():
    """Start the FastAPI backend server and wait until it's ready."""
    env = os.environ.copy()
    env["CHAT_GUARDIAN_DATABASE_URL"] = "sqlite:///./test_browser_tmp.sqlite"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "chat_guardian.api.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )

    # Wait up to 30 seconds for the server to start
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            resp = requests.get(f"{API_BASE}/health", timeout=1)
            if resp.status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("Backend server did not start in time")

    yield proc

    proc.terminate()
    proc.wait(timeout=10)

    # Clean up the temp sqlite db
    db_path = os.path.join(os.path.dirname(__file__), "..", "test_browser_tmp.sqlite")
    if os.path.exists(db_path):
        os.remove(db_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def navigate_and_wait(page, path: str, wait_for_text: str | None = None, timeout: int = 10000):
    """Navigate to a frontend path and optionally wait for visible text."""
    page.goto(f"{FRONTEND_BASE}{path}", wait_until="networkidle")
    if wait_for_text:
        page.wait_for_selector(f"text={wait_for_text}", timeout=timeout)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_dashboard_loads(page):
    """仪表盘页面加载并显示系统状态与 LLM 配置。"""
    navigate_and_wait(page, "/", wait_for_text="ChatGuardian")

    # Sidebar menu should have all 5 nav items
    assert page.locator("text=仪表盘").count() >= 1
    assert page.locator("text=规则管理").count() >= 1
    assert page.locator("text=触发统计").count() >= 1
    assert page.locator("text=消息队列").count() >= 1
    assert page.locator("text=系统配置").count() >= 1

    # Check that backend health info is displayed
    page.wait_for_selector("text=ok", timeout=5000)

    # LLM config card
    page.wait_for_selector("text=Backend", timeout=5000)
    page.wait_for_selector("text=openai_compatible", timeout=5000)


def test_rule_management_create_and_list(page):
    """规则管理：创建一条规则，验证列表显示该规则，并且 API 返回正确数据。"""
    navigate_and_wait(page, "/rules", wait_for_text="新增规则")

    # Open the "新增规则" modal
    page.get_by_role("button", name="新增规则").click()
    page.wait_for_selector("text=规则名称", timeout=5000)

    # Fill in the form
    page.get_by_label("规则名称").fill("BrowserTest Rule")
    page.get_by_label("描述").fill("Created by browser automation test")

    # Click OK
    page.get_by_role("button", name="OK").click()

    # Wait for success notification
    page.wait_for_selector("text=Created", timeout=8000)

    # Rule should appear in the list
    page.wait_for_selector("text=BrowserTest Rule", timeout=5000)

    # Verify backend has the rule via API
    resp = requests.get(f"{API_BASE}/rules/list", timeout=5)
    assert resp.status_code == 200
    rules = resp.json()
    assert any(r["name"] == "BrowserTest Rule" for r in rules), (
        f"Rule not found in API response: {rules}"
    )


def test_rule_matcher_editor_and_group(page):
    """规则匹配器编辑器：展开规则，修改 Matcher 为 AND 组并添加子条件，验证无错误。"""
    navigate_and_wait(page, "/rules", wait_for_text="BrowserTest Rule")

    # Expand the rule — Ant Design Collapse header has role="button" (div, not <button>)
    page.get_by_role("button").filter(has_text="BrowserTest Rule").first.click()
    page.wait_for_selector("text=匹配器", timeout=5000)

    # Click the matcher type Select dropdown (identified by title "🌟 全匹配 (All)")
    page.locator('[title="🌟 全匹配 (All)"]').first.click()
    page.wait_for_selector("text=AND 组 (全部满足)", timeout=5000)
    page.get_by_title("🔵 AND 组 (全部满足)").first.click()

    # AND group label should appear
    page.wait_for_selector("text=AND — 所有条件都要满足", timeout=5000)

    # Add a child leaf condition
    page.get_by_role("button", name="➕ 条件").first.click()

    # The child "All" matcher should be visible
    page.wait_for_selector("text=全匹配 (All)", timeout=5000)

    # Wait for "未保存" badge indicating dirty state (save button enabled)
    page.wait_for_selector("text=未保存", timeout=5000)

    # Click the save button
    page.locator(".ant-btn").filter(has_text="保存").first.click()

    # Wait for Saved notification
    page.wait_for_selector("text=Saved", timeout=15000)

    # Verify backend saved the rule with AND matcher
    resp = requests.get(f"{API_BASE}/rules/list", timeout=5)
    rules = resp.json()
    rule = next((r for r in rules if r["name"] == "BrowserTest Rule"), None)
    assert rule is not None, "Rule not found after save"
    assert rule["matcher"]["type"] == "and", f"Expected AND matcher, got: {rule['matcher']}"


def test_message_queue_page_loads(page):
    """消息队列页面：验证页面加载、Tabs 显示待处理/历史队列。"""
    navigate_and_wait(page, "/queues")

    # Tab labels
    page.wait_for_selector("text=待处理", timeout=5000)
    page.wait_for_selector("text=历史", timeout=5000)

    # Empty state message
    assert page.locator("text=暂无待处理消息").count() >= 1 or page.locator("text=暂无").count() >= 1


def test_trigger_stats_page_loads(page):
    """触发统计页面：验证页面正常加载（无规则触发时显示空状态）。"""
    navigate_and_wait(page, "/stats")

    # Page should load without error - just validate it's accessible
    assert page.url.endswith("/stats")


def test_system_config_page_displays_settings(page):
    """系统配置页面：验证显示当前 LLM 和系统配置。"""
    navigate_and_wait(page, "/config")

    page.wait_for_selector("text=LLM", timeout=5000)
    page.wait_for_selector("text=openai_compatible", timeout=5000)
    page.wait_for_selector("text=gpt-4o-mini", timeout=5000)


def test_rule_delete(page):
    """规则管理：删除测试规则，验证列表中规则消失且 API 确认删除。"""
    navigate_and_wait(page, "/rules", wait_for_text="BrowserTest Rule")

    # Expand the rule — Ant Design Collapse header has role="button" (div, not <button>)
    page.get_by_role("button").filter(has_text="BrowserTest Rule").first.click()
    page.wait_for_selector("text=匹配器", timeout=5000)

    # Click the rule-level 删除 button (has text "删除", as opposed to child matcher X buttons)
    page.locator(".ant-btn").filter(has_text="删除").first.click()

    # Confirm in popconfirm dialog (Ant Design uses "OK" / "Cancel" in English).
    # Use .first to avoid strict-mode failure if other dialog buttons are in the DOM.
    page.wait_for_selector("text=确认删除", timeout=5000)
    page.get_by_role("button", name="OK").first.click()

    # Wait for deletion notification
    page.wait_for_selector("text=Deleted", timeout=8000)

    # Verify backend
    resp = requests.get(f"{API_BASE}/rules/list", timeout=5)
    rules = resp.json()
    assert all(r["name"] != "BrowserTest Rule" for r in rules), (
        "Rule should have been deleted from backend"
    )


def test_backend_no_server_errors(page, start_backend_server):
    """验证所有浏览器操作过程中后端进程未崩溃。"""
    proc = start_backend_server
    assert proc.poll() is None, "Backend server unexpectedly terminated"

    # Final health check
    resp = requests.get(f"{API_BASE}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
