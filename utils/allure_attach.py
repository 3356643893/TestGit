import allure
import os
import json
import shutil
import time
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"


def clear_allure_results(suite=None):
    """清空 allure-results 目录（测试前清理旧结果）"""
    if suite:
        base = REPORTS_DIR / suite
    else:
        base = REPORTS_DIR

    res_path = base / "allure-results"
    log_path = base / "logs"

    for path in [res_path, log_path]:
        if os.path.exists(path):
            for attempt in range(3):
                try:
                    shutil.rmtree(path)
                    break
                except PermissionError:
                    time.sleep(0.5)

    os.makedirs(res_path, exist_ok=True)
    os.makedirs(log_path, exist_ok=True)


def attach_request(req_url, req_method, req_headers, req_body):
    """附加请求信息到 Allure 报告"""

    if isinstance(req_headers, dict):
        req_headers = json.dumps(req_headers, indent=2, ensure_ascii=False)
    if isinstance(req_body, dict):
        req_body = json.dumps(req_body, indent=2, ensure_ascii=False)

    text = f"""
        请求URL：{req_url}
        请求方法：{req_method}
        请求头：{req_headers}
        请求体：{req_body}
    """
    allure.attach(text, name="请求信息", attachment_type=allure.attachment_type.TEXT)

def attach_response(resp_status, resp_text):
    """附加响应信息到 Allure 报告"""
    if isinstance(resp_text, dict):
        resp_text = json.dumps(resp_text, indent=2, ensure_ascii=False)

    text = f"""
        响应状态码：{resp_status}
        响应体：{resp_text}
    """
    allure.attach(text, name="响应信息", attachment_type=allure.attachment_type.TEXT)

def attach_error(errmsg):
    """附加错误信息到 Allure 报告"""
    if isinstance(errmsg, Exception):
        errmsg = traceback.format_exc()

    text = f"错误详情:\n{errmsg}"
    allure.attach(text, name="错误信息", attachment_type=allure.attachment_type.TEXT)
