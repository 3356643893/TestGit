import time
from logging import exception

import requests
from config.config import config as env_config
from utils.allure_attach import attach_request, attach_response, attach_error
from config.log_config import logger

MAX_RESPONSE_ATTACH_LENGTH = 2000


def _is_retryable(exception: Exception) -> bool:
    """判断异常是否可重试：网络错误、超时、5xx"""
    if isinstance(exception, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exception, requests.HTTPError):
        return True
    return False


class ApiResponse:
    """统一响应封装：自动解析 JSON，保留原始响应和耗时"""

    def __init__(self, raw: requests.Response, elapsed_ms: float, url: str = "", method: str = ""):
        """包装原始响应，解析 JSON，记录耗时"""
        self.raw = raw
        self.status_code = raw.status_code
        self.elapsed_ms = round(elapsed_ms, 2)
        self.headers = dict(raw.headers)
        self.text = raw.text
        self.url = url
        self.method = method
        self.path_url = url
        try:
            self.json_data = raw.json()
        except Exception:
            self.json_data = None

    def json(self):
        """返回解析后的 JSON 字典"""
        return self.json_data

    def __repr__(self):
        """调试友好的字符串表示"""
        return f"ApiResponse(status={self.status_code}, elapsed={self.elapsed_ms}ms, url={self.path_url})"


class ApiClient:
    def __init__(self):
        """从 config 读 base_url，初始化 Session 和默认 headers"""
        self.base_url = env_config.get("base_url")
        if not self.base_url:
            raise ValueError("配置文件中未找到 base_url，请检查 env.yaml")
        self.base_url = self.base_url.rstrip("/")

        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/json"
        }
        self.token = None

        default_token = env_config.get("token")
        if default_token:
            self.set_token(default_token)

    def _filter_params(self, params: dict) -> dict:
        """自动过滤 None 值参数，避免脏数据传入接口"""
        if params is None:
            return {}
        return {k: v for k, v in params.items() if v is not None}

    def _request_with_retry(self, method, url, **kwargs):
        """内部请求方法：Mock 模式下走 Mock，否则发真实请求并按配置重试"""
        from utils.mock_handler import is_mock_active
        if is_mock_active():
            return self._mock_request(method, url, **kwargs)

        max_retries = env_config.get("retry.max_attempts", 3)
        retry_wait = env_config.get("retry.wait_seconds", 1)

        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.request(method=method, url=url, **kwargs)
                if resp.status_code in (502, 503, 504):
                    logger.warning(f"收到 {resp.status_code}，第 {attempt}/{max_retries} 次重试...")
                    if attempt < max_retries:
                        time.sleep(retry_wait)
                        continue
                return resp
            except requests.exceptions.RequestException as e:
                if not _is_retryable(e):
                    raise e
                last_exception = e
                logger.warning(f"请求异常 ({type(e).__name__})，第 {attempt}/{max_retries} 次重试...")
                if attempt < max_retries:
                    time.sleep(retry_wait)
                else:
                    raise e
        raise last_exception

    def _mock_request(self, method, url, **kwargs):
        """激活 Mock 时，按 path fragment 匹配场景数据并返回假响应（路径映射由业务侧自行扩展）"""
        from unittest.mock import Mock
        from utils.mock_handler import get_current_scenes, get_scene_data
        import json as _json

        scene_key_map = {}
        scenes = get_current_scenes()
        for path_fragment, scene_key in scene_key_map.items():
            if path_fragment in url and scene_key in scenes:
                data = get_scene_data(scene_key, scenes[scene_key])
                if data:
                    mock_resp = Mock()
                    mock_resp.status_code = 200
                    mock_resp.text = _json.dumps(data, ensure_ascii=False)
                    mock_resp.headers = {"Content-Type": "application/json"}
                    mock_resp.json.return_value = data
                    logger.info(f"[MOCK] {method.upper()} {url} → {data.get('message', 'mock')}")
                    return mock_resp

        logger.info(f"[MOCK] {method.upper()} {url} → 未匹配 Mock 规则，走真实请求")
        return self.session.request(method=method, url=url, **kwargs)

    def send(self, method, path, **kwargs):
        """核心入口：拼接 URL、处理 headers、调用重试逻辑、记录 Allure 和日志"""
        json = kwargs.pop("json", None)
        params = kwargs.pop("params", {})
        headers = kwargs.pop("headers", {})
        timeout = kwargs.pop("timeout", None)
        files = kwargs.pop("files", None)
        data = kwargs.pop("data", None)

        full_path = path.lstrip("/")
        url = f"{self.base_url}/{full_path}"

        params = self._filter_params(params)

        req_headers = self.headers.copy()
        if headers:
            req_headers.update(headers)
        if files:
            req_headers.pop("Content-Type", None)
        if data is not None:
            req_headers.pop("Content-Type", None)
        if timeout is None:
            timeout = env_config.get("timeout", 10)

        try:
            logger.info(f"请求URL：{url} 请求方法：{method.upper()}")
            attach_request(url, method, req_headers, json or data)

            start = time.time()
            resp = self._request_with_retry(
                method=method,
                url=url,
                headers=req_headers,
                json=json,
                params=params,
                data=data,
                files=files,
                timeout=timeout,
                **kwargs
            )
            elapsed_ms = (time.time() - start) * 1000

            resp_text = resp.text
            if len(resp_text) > MAX_RESPONSE_ATTACH_LENGTH:
                resp_text = resp_text[:MAX_RESPONSE_ATTACH_LENGTH] + (
                    f"\n... [截断，原始长度 {len(resp.text)} 字符]"
                    f"\n⚠️ 如需查看完整报错，请登录测试服务器执行: tail -n 200 /path/to/service/error.log"
                )

            logger.info(f"响应码：{resp.status_code} 耗时：{elapsed_ms:.0f}ms")
            attach_response(resp.status_code, resp_text)

            return ApiResponse(raw=resp, elapsed_ms=elapsed_ms, url=url, method=method)

        except Exception as e:
            err_msg = f"请求异常：{str(e)}"
            logger.error(err_msg)
            attach_error(err_msg)
            raise e

    def set_token(self, token):
        """设置鉴权 token"""
        self.token = token
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
            logger.info(f"设置 Bearer token：{token[:50]}...")
        else:
            self.headers.pop("Authorization", None)

    def get_token(self):
        """获取当前 token"""
        return self.token

    def clear_token(self):
        """清除 token 和 cookie"""
        self.token = None
        self.headers.pop("Authorization", None)
        self.session.cookies.clear()
        logger.info("清除 token 与 session cookie")

    def post(self, path, **kwargs):
        """发送 POST 请求"""
        return self.send("post", path, **kwargs)

    def get(self, path, **kwargs):
        """发送 GET 请求"""
        return self.send("get", path, **kwargs)

    def put(self, path, **kwargs):
        """发送 PUT 请求"""
        return self.send("put", path, **kwargs)

    def delete(self, path, **kwargs):
        """发送 DELETE 请求"""
        return self.send("delete", path, **kwargs)