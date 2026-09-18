import json
from datetime import datetime
from pathlib import Path

import pytest
import allure
from playwright.sync_api import sync_playwright
from config.config import config


@pytest.fixture(scope="session")
def ui_base_url():
    """fixture：返回 UI 测试目标的 base_url"""
    return config.get("ui_base_url", "http://127.0.0.1:8080")


@pytest.fixture(scope="session")
def playwright():
    """fixture：pytest-playwright playwright 实例"""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="function")
def browser(playwright):
    """fixture：启动 headless Chromium browser"""
    browser = playwright.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def context(browser, request):
    """fixture：创建隔离的 BrowserContext（自动关闭）"""
    ctx = browser.new_context()
    ctx.tracing.start(screenshots=True, snapshots=True)

    ctx_errors = []
    ctx_console = []
    ctx_network = []

    def on_page_error(err):
        """fixture：注册 page 层 error handler"""
        ctx_errors.append(str(err))

    def on_console(msg):
        """fixture：注册 console message handler（WARNING 以上记录）"""
        if msg.type in ("error", "warning"):
            ctx_console.append(f"[{msg.type}] {msg.text}")

    def on_response(resp):
        """fixture：注册 response handler（失败 API 附加 Allure）"""
        try:
            req = resp.request
            ctx_network.append({
                "url": resp.url,
                "status": resp.status,
                "method": req.method,
                "ok": resp.ok,
            })
        except Exception:
            pass

    ctx.on("page", lambda page: (
        page.on("pageerror", on_page_error),
        page.on("console", on_console),
        page.on("response", on_response),
    ))

    yield ctx

    setattr(request.node, "_page_errors", ctx_errors)
    setattr(request.node, "_page_console", ctx_console)
    setattr(request.node, "_network_logs", ctx_network)


@pytest.fixture(scope="function")
def page(context):
    """fixture：创建隔离的 Page（每个测试独立页面）"""
    page = context.new_page()
    page.set_default_timeout(15000)
    yield page
    page.close()


def _resolve_artifact_dirs(config):
    """解析截图/快照/trace/诊断日志的存储目录（跟随 --alluredir 父目录）"""
    alluredir = config.getoption("--alluredir", default=None)
    if alluredir:
        base = Path(alluredir).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent.parent / "reports"
    shot_dir = base / "screenshots"
    html_dir = base / "html_snapshots"
    trace_dir = base / "traces"
    net_dir = base / "network_logs"
    for d in [shot_dir, html_dir, trace_dir, net_dir]:
        d.mkdir(parents=True, exist_ok=True)
    return shot_dir, html_dir, trace_dir, net_dir


def _safe_name(nodeid: str) -> str:
    """将 pytest 用例 nodeid 转为合法文件名（替换 Windows 不支持的字符）"""
    return nodeid.replace("::", "_").replace("/", "_").replace("\\", "_")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """UI 专属 hook：用例失败时自动截图 / HTML 快照 / Trace / 诊断日志"""
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call" and rep.failed:
        if "page" not in item.funcargs:
            return

        page = item.funcargs["page"]
        shot_dir, html_dir, trace_dir, net_dir = _resolve_artifact_dirs(item.config)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = _safe_name(item.nodeid)

        try:
            shot_path = shot_dir / f"{safe}_{ts}.png"
            page.screenshot(path=str(shot_path), full_page=True)
            allure.attach.file(
                str(shot_path),
                name=f"失败截图: {item.nodeid}",
                attachment_type=allure.attachment_type.PNG
            )
        except Exception as e:
            allure.attach(f"截图失败: {e}", name="截图异常", attachment_type=allure.attachment_type.TEXT)

        try:
            html_path = html_dir / f"{safe}_{ts}.html"
            html_path.write_text(page.content(), encoding="utf-8")
            allure.attach.file(
                str(html_path),
                name=f"HTML快照: {item.nodeid}",
                attachment_type=allure.attachment_type.HTML
            )
        except Exception as e:
            allure.attach(f"HTML快照失败: {e}", name="快照异常", attachment_type=allure.attachment_type.TEXT)

        try:
            trace_path = trace_dir / f"{safe}_{ts}.zip"
            context = page.context
            if context.tracing:
                context.tracing.stop(path=str(trace_path))
                allure.attach.file(
                    str(trace_path),
                    name=f"Playwright Trace: {item.nodeid}",
                    attachment_type=allure.attachment_type.ZIP
                )
        except Exception:
            pass

        try:
            page_errors = getattr(item, "_page_errors", [])
            page_console = getattr(item, "_page_console", [])
            net_logs = getattr(item, "_network_logs", [])

            bundle = {
                "test": item.nodeid,
                "timestamp": ts,
                "page_url": page.url,
                "errors": page_errors,
                "console": page_console,
                "network": net_logs[-50:],
            }
            net_path = net_dir / f"{safe}_{ts}.json"
            net_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
            allure.attach(
                json.dumps(bundle, ensure_ascii=False, indent=2),
                name=f"诊断日志: {item.nodeid}",
                attachment_type=allure.attachment_type.JSON
            )
        except Exception:
            pass