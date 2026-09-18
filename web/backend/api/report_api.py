"""
报告查看路由
- 按 suite 查看：GET /api/report/suite/{suite}
- 按任务查看：GET /api/report/task/{task_id}
- 列表扫描：  GET /api/report/list
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import os

from web.backend.service.task_service import BASE_DIR, get_task_status, list_available_reports

router = APIRouter()


@router.get("/suite/{suite}", response_class=HTMLResponse, summary="按 suite 查看报告")
def get_suite_report(suite: str):
    """按测试套件返回聚合报告统计"""
    if suite == "all":
        raise HTTPException(
            status_code=400,
            detail="all 模式无单一报告，请分别指定 api / ui / performance，或通过 GET /api/report/list 查看全部"
        )
    valid = ("api", "ui", "performance")
    if suite not in valid:
        raise HTTPException(status_code=400, detail=f"无效的 suite: {suite}")
    index_path = BASE_DIR / "reports" / suite / "allure-report" / "index.html"
    if not index_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{suite} 报告不存在，请先运行 python run.py {suite}"
        )
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/task/{task_id}", response_class=HTMLResponse, summary="按任务 ID 查看报告")
def get_task_report(task_id: str):
    """按任务 ID 返回单次执行的详细报告"""
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    reports = task.get("reports", {})
    if not reports:
        raise HTTPException(
            status_code=404,
            detail=f"任务 {task_id} 报告不存在（可能任务未完成或失败）"
        )

    suite = task.get("suite", "")
    if suite == "all":
        suites_html = "".join(
            f'<li><a href="/api/report/suite/{s}">{s.upper()}</a> - <code>{info["report_index"]}</code></li>'
            for s, info in reports.items()
        )
        html = f"""
        <html><head><meta charset="utf-8"><title>all 模式报告</title></head>
        <body><h2>任务 {task_id}（all 模式）的报告</h2>
        <ul>{suites_html}</ul></body></html>
        """
        return HTMLResponse(content=html)

    report_index = reports.get(suite, {}).get("report_index")
    if not report_index or not Path(report_index).exists():
        raise HTTPException(
            status_code=404,
            detail=f"任务 {task_id} 报告不存在（可能任务未完成或失败）"
        )
    with open(report_index, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/list", summary="扫描可用报告列表")
def get_report_list():
    """列出历史报告（支持分页）"""
    reports = list_available_reports()
    return {"code": 0, "message": "查询成功", "data": reports}
