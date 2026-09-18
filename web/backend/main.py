"""
平台后端入口
- 启动 FastAPI 服务器
- 启动定时调度器（可选）
- 允许跨域（前端页面可能在另一个端口）
"""
import os
import sys


BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI, HTTPException
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler
)
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from web.backend.api import task_api, report_api
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    try:
        from core.scheduler_task import start_scheduler
        start_scheduler()
    except Exception as e:
        print(f"[警告] 调度器启动失败: {e}")
    yield

app = FastAPI(
    title="自动化测试平台 API",
    description="提供测试任务提交、状态查询、报告查看等能力",
    version="1.0.0",
    lifespan=lifespan
)

# ── 允许跨域（前端页面可能通过不同端口访问） ─────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 生产环境请改为具体域名，如 ["http://localhost:8080"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ─────────────────────────────────────
app.include_router(task_api.router, prefix="/api/task", tags=["测试任务"])
app.include_router(report_api.router, prefix="/api/report", tags=["报告管理"])


# ── 根路径健康检查 ────────────────────────────────
@app.get("/", summary="健康检查")
def root():
    """根路由健康检查"""
    return {
        "service": "自动化测试平台",
        "status": "running",
        "docs": "/docs",           # FastAPI 自动生成的 Swagger 文档
        "redoc": "/redoc",
    }

# @app.exception_handler(StarletteHTTPException)
# async def custom_http_exception_handler(request, exc):
#     logger.error(f"HTTP Error: {exc.status_code} - {exc.detail}")
#     return await http_exception_handler(request, exc)
#
# @app.exception_handler(ValidationError)
# async def validation_exception_handler(request, exc):
#     logger.error(f"Validation Error: {exc}")
#     return await request_validation_exception_handler(request, exc)
#
# @app.exception_handler(Exception)
# async def general_exception_handler(request, exc):
#     logger.error(f"Unexpected Error: {exc}", exc_info=True)
#     return JSONResponse(
#         status_code=500,
#         content={"code": -1, "message": "服务器内部错误", "data": None}
#     )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
