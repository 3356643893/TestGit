"""
测试任务服务层
职责：
  1. 异步执行 run.py（不阻塞 HTTP 请求）
  2. 维护任务状态：PENDING / RUNNING / SUCCESS / FAILED
  3. 记录执行历史（内存字典，可扩展到数据库）

注意：
  不负责跑 pytest / 生成报告 / 发邮件 —— 这些全由 run.py 统一处理
  web 只做"调度 + 展示"，真正的测试能力在 run.py / testcases/ 里
"""
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import os

_tasks: Dict[str, dict] = {}

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SUITE_MAP = {
    "api": "api",
    "ui": "ui",
    "performance": "performance",
    "all": "all",
}


def _suite_to_report_dir(suite: str) -> Optional[str]:
    valid = ("api", "ui", "performance")
    if suite in valid:
        return str(BASE_DIR / "reports" / suite / "allure-report")
    return None


def _all_report_dirs() -> Dict[str, str]:
    valid = ("api", "ui", "performance")
    return {s: str(BASE_DIR / "reports" / s / "allure-report") for s in valid}


def _run_task_async(task_id: str, suite: str = "api"):
    """_suite_to_report_dir"""
    _tasks[task_id]["status"] = "RUNNING"
    _tasks[task_id]["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        cmd = [sys.executable, "run.py", suite]

        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=30 * 60,
            env={**os.environ.copy(), "PYTHONPATH": str(BASE_DIR)}
        )

        report_info: Dict[str, object] = {}

        if suite == "all":
            dirs = _all_report_dirs()
            for s, d in dirs.items():
                idx = Path(d) / "index.html"
                if idx.exists():
                    report_info[s] = {"report_path": d, "report_index": str(idx)}
        else:
            report_dir = _suite_to_report_dir(suite)
            if report_dir:
                report_index = Path(report_dir) / "index.html"
                if report_index.exists():
                    report_info[suite] = {"report_path": report_dir, "report_index": str(report_index)}

        _tasks[task_id].update({
            "status": "SUCCESS" if result.returncode == 0 else "FAILED",
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reports": report_info,
            "return_code": result.returncode,
            "stdout_tail": result.stdout[-3000:] if result.stdout else "",
            "stderr_tail": result.stderr[-2000:] if result.stderr else "",
        })

    except subprocess.TimeoutExpired:
        _tasks[task_id].update({
            "status": "TIMEOUT",
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": "任务执行超时（超过 30 分钟）"
        })
    except Exception as e:
        _tasks[task_id].update({
            "status": "FAILED",
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(e)
        })


# ─────────────────────────────────────────────
# 对外 API
# ─────────────────────────────────────────────
def submit_task(suite: str = "api") -> dict:
    """后台服务层：创建任务、入队执行、返回 task_id"""
    if suite not in SUITE_MAP:
        suite = "api"

    import uuid
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "task_id": task_id,
        "suite": suite,
        "status": "PENDING",
        "start_time": None,
        "end_time": None,
        "reports": {},
        "return_code": None,
        "stdout_tail": None,
        "stderr_tail": None,
        "error": None,
    }

    thread = threading.Thread(target=_run_task_async, args=(task_id, suite))
    thread.daemon = True
    thread.start()

    return _tasks[task_id]


def get_task_status(task_id: str) -> Optional[dict]:
    """后台服务层：查询任务执行状态"""
    return _tasks.get(task_id)


def get_all_tasks(limit: int = 50) -> list:
    tasks = list(_tasks.values())
    tasks.sort(key=lambda x: x.get("start_time", "") or "", reverse=True)
    return tasks[:limit]


def list_available_reports() -> list:
    reports = []
    for suite in ["api", "ui", "performance"]:
        index = Path(BASE_DIR) / "reports" / suite / "allure-report" / "index.html"
        if index.exists():
            mtime = datetime.fromtimestamp(index.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            reports.append({
                "suite": suite,
                "mtime": mtime,
                "report_url": f"/api/report/suite/{suite}",
            })
    return reports
