import json
import re
import allure
from typing import Any, Optional


@allure.step("断言 HTTP 状态码：期望 {expected}")
def assert_status_code(response, expected: int = 200):
    """断言 HTTP 状态码"""
    assert response.status_code == expected, (
        f"HTTP 状态码错误，期望 {expected}，实际 {response.status_code}\n"
        f"响应内容：{response.text}"
    )


@allure.step("断言业务状态码：期望 {expected}")
def assert_code(response_json, expected: int, key: str = "code"):
    """断言业务码（响应体 code 字段），自动兼容 ApiResponse"""
    if hasattr(response_json, 'json_data'):
        response_json = response_json.json_data
    actual = response_json.get(key)
    assert actual == expected, (
        f"业务状态码错误，期望 {expected}，实际 {actual}\n"
        f"完整响应：{json.dumps(response_json, ensure_ascii=False, indent=2)}"
    )


@allure.step("断言响应字段存在：{field_path}")
def assert_field_exists(response_json: dict, field_path: str):
    """断言响应字段存在（支持点号路径嵌套访问）"""
    parts = field_path.split(".")
    value = response_json
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise AssertionError(
                f"字段 [{field_path}] 不存在。完整响应：{json.dumps(response_json, ensure_ascii=False, indent=2)}"
            )
    return value


@allure.step("断言响应字段值：{field_path} = {expected}")
def assert_field_value(response_json: dict, field_path: str, expected: Any):
    """断言响应字段值等于期望值"""
    actual = assert_field_exists(response_json, field_path)
    assert actual == expected, (
        f"字段 [{field_path}] 值不匹配：期望 {expected}，实际 {actual}"
    )


@allure.step("断言字段类型：{field_path} 期望 {expected_type}")
def assert_field_type(response_json: dict, field_path: str, expected_type: type):
    """断言响应字段类型符合预期（支持 float 兼容 int）"""
    actual = assert_field_exists(response_json, field_path)
    type_map = {
        str: (str,),
        int: (int,),
        float: (int, float),
        bool: (bool,),
        dict: (dict,),
        list: (list,),
        None: (type(None),),
    }
    allowed = type_map.get(expected_type, (expected_type,))
    assert isinstance(actual, allowed), (
        f"字段 [{field_path}] 类型不匹配：期望 {expected_type.__name__}，"
        f"实际 {type(actual).__name__}，值: {actual}"
    )


@allure.step("断言数值范围：{field_path} ∈ [{min_val}, {max_val}]")
def assert_number_range(response_json: dict, field_path: str,

                        min_val: Optional[float] = None,
                        max_val: Optional[float] = None):
    """断言数值字段在 [min, max] 区间内（端点包含）"""
    actual = assert_field_exists(response_json, field_path)
    assert isinstance(actual, (int, float)), (
        f"字段 [{field_path}] 不是数值类型: {type(actual).__name__}"
    )
    if min_val is not None:
        assert actual >= min_val, f"字段 [{field_path}] = {actual} < 最小值 {min_val}"
    if max_val is not None:
        assert actual <= max_val, f"字段 [{field_path}] = {actual} > 最大值 {max_val}"


@allure.step("断言正则匹配：{field_path} 匹配 {pattern}")
def assert_field_match(response_json: dict, field_path: str, pattern: str):
    """断言字段值匹配正则表达式"""
    actual = assert_field_exists(response_json, field_path)
    assert isinstance(actual, str), f"字段 [{field_path}] 不是字符串，无法正则匹配: {type(actual).__name__}"
    assert re.search(pattern, actual), (
        f"字段 [{field_path}] = '{actual}' 不匹配正则 '{pattern}'"
    )


@allure.step("断言列表长度：{field_path} 长度 ∈ [{min_len}, {max_len}]")
def assert_list_length(response_json: dict, field_path: str,

                       min_len: Optional[int] = None,
                       max_len: Optional[int] = None):
    """断言列表字段长度在 [min_len, max_len] 区间"""
    actual = assert_field_exists(response_json, field_path)
    assert isinstance(actual, list), f"字段 [{field_path}] 不是列表类型: {type(actual).__name__}"
    length = len(actual)
    if min_len is not None:
        assert length >= min_len, f"列表 [{field_path}] 长度 {length} < 最小值 {min_len}"
    if max_len is not None:
        assert length <= max_len, f"列表 [{field_path}] 长度 {length} > 最大值 {max_len}"


@allure.step("断言列表包含元素：{field_path} 包含 {expected_item}")
def assert_list_contains(response_json: dict, field_path: str, expected_item: Any):
    """断言列表字段包含指定元素"""
    actual = assert_field_exists(response_json, field_path)
    assert isinstance(actual, list), f"字段 [{field_path}] 不是列表类型: {type(actual).__name__}"
    assert expected_item in actual, f"列表 [{field_path}] 不包含元素 {expected_item}"


@allure.step("断言响应耗时：期望 < {max_ms}ms")
def assert_response_time(response, max_ms: int = 2000):
    """断言响应耗时不超过阈值（无 elapsed_ms 属性则跳过）"""
    actual_ms = getattr(response, "elapsed_ms", None)
    if actual_ms is None:
        return
    assert actual_ms <= max_ms, (
        f"接口响应耗时超标：期望 ≤ {max_ms}ms，实际 {actual_ms}ms"
    )


@allure.step("断言自定义条件：{condition_desc}")
def assert_that(condition: bool, condition_desc: str, detail: str = ""):
    """自定义条件断言（condition 必须是 bool，不能传 lambda）"""
    msg = f"断言失败: {condition_desc}"
    if detail:
        msg += f"\n{detail}"
    assert isinstance(condition, bool), (
        f"condition 必须是 bool，实际是 {type(condition).__name__}。"
        f"你是不是传了 lambda 或忘了加括号？"
    )
    assert condition, msg