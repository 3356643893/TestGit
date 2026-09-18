import json
import csv
import logging
from pathlib import Path

from config.config import config

logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_path(file_name, sub_dir=""):
    """定位数据文件路径（优先绝对路径，否则从 data/ 目录找）"""
    path = BASE_DIR / sub_dir / file_name
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在: {path}")
    return path


def load_json(file_name, sub_dir=""):
    """从 JSON 文件加载测试数据"""
    with open(_resolve_path(file_name, sub_dir), "r", encoding="utf-8") as f:
        return json.load(f)


def load_yaml(file_name, sub_dir=""):
    """从 YAML 文件加载测试数据"""
    import yaml
    with open(_resolve_path(file_name, sub_dir), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_csv(file_name, sub_dir=""):
    """从 CSV 文件加载测试数据，自动返回 dict 列表"""
    path = _resolve_path(file_name, sub_dir)
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def load_from_file(file_name, sub_dir=""):
    """按文件后缀自动分发到 load_json/load_yaml/load_csv"""
    ext = Path(file_name).suffix.lower()
    if ext in (".json",):
        return load_json(file_name, sub_dir)
    elif ext in (".yaml", ".yml"):
        return load_yaml(file_name, sub_dir)
    elif ext in (".csv",):
        return load_csv(file_name, sub_dir)
    else:
        raise ValueError(f"不支持的数据文件格式 '{ext}'，支持: .json / .yaml / .csv")


def load_from_db(sql, args=None):
    """从数据库执行 SQL 并返回结果（支持多驱动）"""
    from core.db_handler import DBHandler
    with DBHandler() as db:
        return db.fetch_all(sql, args)


def parametrize(

    source=None,
    file=None,
    sub_dir="",
    sql=None,
    args=None,
    fallback_file=None,
    fallback_sub_dir="",
    key=None,
    ids=None,
):
    """统一数据驱动入口 —— 支持文件 / DB / 自动 fallback

    数据源优先级: source > sql(可 fallback) > file > fallback_file

    Args:
        source:       直接传 Python list（最低优先级，做默认值）
        file:         指定数据文件（.json / .yaml / .csv），sub_dir 是相对于项目根的子目录
        sub_dir:      文件所在子目录
        sql:          SQL 查询语句（从 DB 拉数据）
        args:         SQL 参数 dict
        fallback_file: 当 DB 不可用时，回退读取这个文件
        fallback_sub_dir: fallback 文件的子目录
        key:          如果每条数据是 dict，提取这个 key 的值做返回

    Returns:
        list —— 直接传给 @pytest.mark.parametrize 的 argvalues

    Examples:
        # 方式1 — 从文件
        @pytest.mark.parametrize("data", parametrize(file="success.json", sub_dir="data/api_data/login"), ids=lambda d: d["case_name"])

        # 方式2 — 从 DB
        @pytest.mark.parametrize("row", parametrize(sql="SELECT phone, password FROM test_accounts WHERE env=%(env)s", args={"env": "test"}))

        # 方式3 — DB 优先，不可用时自动回退文件 ✨
        @pytest.mark.parametrize("data", parametrize(
            sql="SELECT * FROM test_login_cases WHERE env='test' AND active=1",
            fallback_file="success.json",
            fallback_sub_dir="data/api_data/login"
        ))

        # 方式4 — 直接传 list
        @pytest.mark.parametrize("val", parametrize(source=[1, 2, 3]))
    """
    data = None

    if sql is not None:
        try:
            data = load_from_db(sql, args)
            logger.info(f"parametrize: 从 DB 拉取 {len(data) if data else 0} 条数据")
        except Exception as e:
            logger.warning(f"parametrize: DB 查询失败 ({e})")
            if fallback_file is not None:
                logger.warning(f"parametrize: 回退到文件 {fallback_file}")
                data = load_from_file(fallback_file, fallback_sub_dir)
            else:
                raise RuntimeError(
                    f"DB 查询失败且未提供 fallback_file，无法获取测试数据\n"
                    f"SQL: {sql}\n错误: {e}"
                )

    elif file is not None:
        data = load_from_file(file, sub_dir)
        logger.info(f"parametrize: 从文件 {sub_dir}/{file} 加载 {len(data) if data else 0} 条")

    elif source is not None:
        data = source

    elif fallback_file is not None:
        data = load_from_file(fallback_file, fallback_sub_dir)
        logger.info(f"parametrize: 从 fallback 文件 {fallback_sub_dir}/{fallback_file} 加载")

    else:
        raise ValueError("必须指定 source / file / sql / fallback_file 其中之一")

    if key:
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            data = [item[key] for item in data]

    if ids is None and isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        case_name_candidates = ["case_name", "name", "id", "phone", "key"]
        for cn in case_name_candidates:
            if cn in data[0]:
                ids = lambda row, _cn=cn: str(row.get(_cn, ""))
                break

    return data
