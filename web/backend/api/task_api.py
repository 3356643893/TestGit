"""
测试任务路由层
- 只做参数接收/校验 → 调 service → 返回响应
- 不写任何业务逻辑
"""
from fastapi import APIRouter, HTTPException
from web.backend.service.task_service import (
    submit_task, get_task_status, get_all_tasks, BASE_DIR
)
from web.backend.schemas.task_schema import SubmitTaskRequest, ApiResponse

router = APIRouter()


@router.post("/submit", response_model=ApiResponse, summary="提交测试任务（异步）")
def submit_test_task(request: SubmitTaskRequest):
    """接收前端提交的测试任务，返回 task_id"""
    res = submit_task(request.suite)
    return {"code": 0, "message": "任务提交成功", "data": res}


@router.get("/status/{task_id}", summary="查询任务状态")
def get_task_status_api(task_id: str):
    """按 task_id 轮询任务状态"""
    res = get_task_status(task_id)
    if res:
        return {"code": 0, "message": "查询成功", "data": res}
    return {"code": -1, "message": f"任务 {task_id} 不存在"}


@router.get("/history", summary="查询历史任务列表")
def get_task_list(limit: int = 50):
    """列出所有历史任务（支持分页/状态筛选）"""
    tasks = get_all_tasks(limit=limit)
    return {"code": 0, "message": "查询成功", "data": tasks}
