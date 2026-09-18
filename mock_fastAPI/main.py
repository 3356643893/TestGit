import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from mock_fastAPI.api.mock_api import router as auth_router

app = FastAPI(
    title="Mock后端服务（测试左移专用）",
    description="开发还没好时，假装成后端接口返回假数据。\n完全独立，零耦合真实数据库和测试框架。",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/", summary="健康检查")
def root():
    """根路由健康检查"""
    return {
        "service": "Mock后端服务",
        "role": "测试左移假数据",
        "status": "running",
        "port": 8001,
        "docs": "/docs",
    }


if __name__ == "__main__":
    uvicorn.run(
        "mock_fastAPI.main:app",
        host="127.0.0.1",
        port=8001,
        reload=True
    )
