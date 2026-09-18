import yaml
from pathlib import Path


def get_yaml_data(file_name, sub_dir=""):
    """读取 YAML 文件并返回 dict，支持指定子目录"""

    base_dir = Path(__file__).resolve().parent.parent
    file_path = base_dir / sub_dir / file_name
    if not file_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML 格式错误: {file_path} — {e}")
