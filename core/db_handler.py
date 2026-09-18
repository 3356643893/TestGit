
DRIVER_MAP = {
    "mysql": {
        "module": "pymysql",
        "sqlalchemy_driver": "mysql+pymysql",
        "default_port": 3306,
        "default_charset": "utf8mb4",
    },
    "postgresql": {
        "module": "psycopg2",
        "sqlalchemy_driver": "postgresql+psycopg2",
        "default_port": 5432,
    },
    "postgres": {
        "module": "psycopg2",
        "sqlalchemy_driver": "postgresql+psycopg2",
        "default_port": 5432,
    },
}


def _get_config():
    """延迟导入 config.config 避免循环依赖，返回 Config 单例"""
    from config.config import config
    return config


def _get_driver_config(driver_name):
    """根据驱动名返回 DRIVER_MAP 映射（sqlalchemy 驱动、默认端口等）"""
    if driver_name not in DRIVER_MAP:
        raise ValueError(
            f"不支持的数据库驱动 '{driver_name}'，支持: {list(DRIVER_MAP.keys())}"
        )
    return DRIVER_MAP[driver_name]


def _import_driver_module(driver_name):
    """动态 import 底层数据库驱动（pymysql / psycopg2），未安装时给出 pip 提示"""
    info = _get_driver_config(driver_name)
    mod_name = info["module"]
    try:
        return __import__(mod_name)
    except ImportError:
        hint = ""
        if driver_name in ("postgresql", "postgres"):
            hint = "  → 请执行: pip install psycopg2-binary"
        raise ImportError(
            f"数据库驱动 '{mod_name}' 未安装{hint}\n"
            f"当前 driver 配置为 '{driver_name}'，缺少底层连接库"
        ) from None


class DBHandler:
    """原生数据库连接（适合简单 SQL 查询、事务回滚测试）"""

    def __init__(self):
        """读取 db 配置，校验 driver，立即建立数据库连接"""
        env_config = _get_config()
        self.db_conf = env_config.get("db", {})
        if not self.db_conf:
            raise ValueError(f"当前环境配置中未找到数据库配置：{env_config.env}")

        self.driver = self.db_conf.get("driver", "mysql")
        self.driver_info = _get_driver_config(self.driver)
        self.conn = None
        self.cursor = None
        self._init_conn()

    def _init_conn(self):
        """根据 driver 选择参数，建立连接并创建 DictCursor"""
        db_module = _import_driver_module(self.driver)

        common_kwargs = {
            "host": self.db_conf["host"],
            "port": self.db_conf.get("port", self.driver_info["default_port"]),
            "user": self.db_conf.get("user", "root"),
            "password": self.db_conf.get("password", ""),
            "database": self.db_conf["database"],
        }

        if self.driver == "mysql":
            self.conn = db_module.connect(
                **common_kwargs,
                autocommit=False,
                charset=self.db_conf.get("charset", "utf8mb4"),
                cursorclass=db_module.cursors.DictCursor,
            )
        elif self.driver in ("postgresql", "postgres"):
            self.conn = db_module.connect(**common_kwargs)
        else:
            raise ValueError(f"不支持的 driver: {self.driver}")

        self.cursor = self.conn.cursor()

    def execute(self, sql, args=None, fetch=True):
        """执行 SQL：fetch=True 返回查询结果（list[dict]），False 执行写操作并自动 allure.attach"""
        from config.log_config import logger
        import allure
        from utils.allure_attach import attach_error

        try:
            logger.info(f"执行SQL：{sql} 参数：{args}")
            allure.attach(
                f"SQL语句：{sql}\n参数：{args}",
                name="数据库SQL",
                attachment_type=allure.attachment_type.TEXT,
            )
            self.cursor.execute(sql, args)
            if fetch:
                if self.driver == "mysql":
                    return self.cursor.fetchall()
                else:
                    cols = [desc[0] for desc in self.cursor.description]
                    return [dict(zip(cols, row)) for row in self.cursor.fetchall()]
        except Exception as e:
            err_msg = f"数据库执行异常：{str(e)}"
            logger.error(err_msg)
            attach_error(err_msg)
            self.conn.rollback()
            raise e

    def fetch_all(self, sql, args=None):
        """查询并返回所有结果行（list[dict]），空则返回 []"""
        return self.execute(sql, args, fetch=True)

    def fetch_one(self, sql, args=None):
        """查询并返回首行结果（dict 或 None）"""
        res = self.execute(sql, args, fetch=True)
        return res[0] if res else None

    def fetch_val(self, sql, args=None):
        """查询并返回单个标量值（首行首列，None 表示无结果）"""
        row = self.fetch_one(sql, args)
        return list(row.values())[0] if row else None

    def commit(self):
        """提交事务"""
        self.conn.commit()

    def rollback(self):
        """回滚事务"""
        self.conn.rollback()

    def close(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """上下文管理器入口，返回 self，支持 with DBHandler() as db 用法"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，自动关闭 cursor 和 connection"""
        self.close()


def get_sqlalchemy_url():
    """根据当前环境的 db 配置拼接 SQLAlchemy URL（用于 ORM Engine 创建）"""
    from sqlalchemy.engine import URL

    env_config = _get_config()
    db_config = env_config.get("db", {})
    driver_name = db_config.get("driver", "mysql")
    driver_info = _get_driver_config(driver_name)

    return URL.create(
        drivername=driver_info["sqlalchemy_driver"],
        username=db_config.get("user", "root"),
        password=db_config.get("password", ""),
        host=db_config.get("host", "127.0.0.1"),
        port=db_config.get("port", driver_info["default_port"]),
        database=db_config.get("database", ""),
    )