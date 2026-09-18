"""
请求/响应模型（Pydantic BaseModel）
"""
from pydantic import BaseModel, Field
from typing import Optional


class SubmitTaskRequest(BaseModel):
    suite: str = Field(
        ...,
        pattern="^(api|ui|performance|all)$",
        description="要运行的测试套件: api / ui / performance / all"
    )


class TaskResponse(BaseModel):
    task_id: str
    suite: str
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    report_path: Optional[str] = None
    report_index: Optional[str] = None
    return_code: Optional[int] = None
    stdout_tail: Optional[str] = None
    stderr_tail: Optional[str] = None
    error: Optional[str] = None


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[TaskResponse] = None