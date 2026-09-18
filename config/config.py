import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from utils.yaml_util import get_yaml_data

BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env（敏感凭证）
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv(BASE_DIR / ".env.example")

DEFAULTS_FILE = Path(__file__).resolve().parent / "defaults.yaml"   # Layer 1: 框架默认值
ENV_YAML_FILE = Path(__file__).resolve().parent / "env.yaml"        # Layer 2: 环境差异


def _resolve_active_env(raw: dict) -> str:
    cli_env = None
    for i, arg in enumerate(sys.argv):
        if arg == "--env" and i + 1 < len(sys.argv):
            cli_env = sys.argv[i + 1]
            break
        if arg.startswith("--env="):
            cli_env = arg.split("=", 1)[1]
            break
    if cli_env:
        valid_envs = list(raw.get("environment", {}).keys())
        if cli_env not in valid_envs:
            raise ValueError(f"无效环境 '{cli_env}'，可用: {valid_envs}")
        return cli_env
    return os.getenv("APP_ENV", raw.get("env", "test"))


class Config:
    """三层配置加载: defaults.yaml → env.yaml → .env，deep_merge 深度覆盖"""

    def __init__(self):
        """加载三层配置：defaults.yaml → env.yaml → .env，deep_merge 后校验必填项"""
        env_raw = get_yaml_data("env.yaml", "config") or {}

        # 读 defaults.yaml
        defaults = {}
        if DEFAULTS_FILE.exists():
            import yaml as _yaml
            defaults = _yaml.safe_load(DEFAULTS_FILE.read_text(encoding="utf-8")) or {}

        self.env = _resolve_active_env(env_raw)
        global_cfg = env_raw.get("global", {})
        env_cfg = env_raw.get("environment", {}).get(self.env, {})

        # 三层 merge: defaults → global → environment
        self.data = self.deep_merge(defaults, global_cfg)
        self.data = self.deep_merge(self.data, env_cfg)

        self._apply_env_overrides()    # .env 覆盖敏感凭证
        self.validate_config()         # 启动时校验必填项

    def _apply_env_overrides(self):
        """从 .env 读取敏感凭证覆盖 config.data：DB 账号 → Token → 通知凭证"""
        db = self.data.get("db") or {}
        env_user = os.getenv(f"{self.env.upper()}_DB_USER") or os.getenv("DB_USER")
        env_pass = os.getenv(f"{self.env.upper()}_DB_PASSWORD") or os.getenv("DB_PASSWORD")
        if env_user:
            db["user"] = env_user
        if env_pass:
            db["password"] = env_pass
        if db:
            self.data["db"] = db

        token = os.getenv("APP_TOKEN")
        if token:
            self.data["token"] = token

        notify = self.data.get("notify") or {}
        for key, env_var in [
            ("mail_password", "SMTP_PASSWORD"),
            ("lark_webhook", "LARK_WEBHOOK"),
            ("dingtalk_webhook", "DINGTALK_WEBHOOK"),
        ]:
            val = os.getenv(env_var)
            if val:
                notify[key] = val
        if notify:
            self.data["notify"] = notify

    def deep_merge(self, base: dict, override: dict) -> dict:
        """递归深度合并两个字典：override 覆盖 base，子字典也递归合并"""
        merged = base.copy()
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self.deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def get(self, key, default=None):
        """支持点号路径: config.get('db.host')"""
        if "." in key:
            parts = key.split(".")
            value = self.data
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value
        return self.data.get(key, default)

    def validate_config(self):
        """启动时校验必填项（base_url、db、log、notify），缺失或非法直接抛 ValueError"""
        SUPPORTED_DB_DRIVERS = {"mysql", "postgresql", "postgres"}

        required_checks = [
            ("base_url", "base_url"),
            ("db.host", "数据库 host"),
            ("db.database", "数据库 database"),
            ("db.driver", "数据库 driver"),
            ("log.log_level", "日志级别"),
            ("log.dir", "日志目录"),
            ("notify.mail_to", "告警邮箱"),
        ]
        missing = []
        for key_path, desc in required_checks:
            val = self.get(key_path)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                missing.append(f"{desc} ({key_path})")
        if missing:
            raise ValueError(
                f"当前环境 [{self.env}] 缺少以下必填配置:\n  " + "\n  ".join(missing)
            )

        driver = self.get("db.driver")
        if driver not in SUPPORTED_DB_DRIVERS:
            raise ValueError(
                f"当前环境 [{self.env}] 数据库 driver '{driver}' 不支持，支持: {SUPPORTED_DB_DRIVERS}"
            )

    def __getitem__(self, key):
        """支持 config['db.host'] 下标访问（等价于 get，取不到返回 None）"""
        return self.get(key)

    def __contains__(self, key):
        """支持 'db.host' in config 成员判断"""
        try:
            self.get(key)
            return True
        except:
            return False


config = Config()