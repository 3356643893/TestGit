import pytest


def pytest_addoption(parser):
    """注册 pytest --env 命令行参数，用于指定测试环境"""
    parser.addoption("--env", action="store", default=None, help="指定运行环境: test / prod")