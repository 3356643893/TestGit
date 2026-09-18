import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_json_data(file_name, sub_dir=""):
    """加载 JSON 测试数据文件

    推荐新代码用统一入口: from utils.data_driver import load_json / parametrize
    """

    base_dir = Path(__file__).resolve().parent.parent
    file_path = base_dir / sub_dir / file_name
    if not file_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 格式错误: {file_path} — {e}")