import functools
import time
import traceback


def retry(times: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """
    通用重试装饰器：捕获指定异常，等待 delay 秒后重试，最多重试 times 次。
    用法:
        @retry(times=3, delay=2.0)
        def flaky_api_call():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_err = e
                    if attempt < times:
                        time.sleep(delay)
                    else:
                        raise
            raise last_err
        return wrapper
    return decorator


def db_aware(transactional: bool = False):
    """
    数据库感知装饰器：自动从 config 获取当前环境的 db 配置，
    注入到被装饰函数的 kwargs 中（key='db_config'）。
    transactional=True 时自动开启事务，函数返回后提交，异常时回滚。
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from config.config import config
            db_cfg = config.get("db") or {}

            if transactional:
                from core.db_handler import DBHandler
                db = DBHandler()
                try:
                    kwargs["db_config"] = db_cfg
                    kwargs["db"] = db
                    result = func(*args, **kwargs)
                    db.commit()
                    return result
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
            else:
                kwargs["db_config"] = db_cfg
                return func(*args, **kwargs)
        return wrapper
    return decorator


def with_token(username: str = None, token_key: str = "Authorization"):
    """
    Token 注入装饰器：自动从 token_pool 获取指定用户的 token，
    注入到被装饰函数的 kwargs["headers"][token_key] 中。
    如果 token 已过期或不存在，返回 None（由调用方处理）。
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from utils.token_cache import token_pool
            user = username or kwargs.get("username")
            token = None
            if user:
                token = token_pool.acquire(user)

            headers = kwargs.get("headers") or {}
            if token:
                headers[token_key] = token
            kwargs["headers"] = headers
            return func(*args, **kwargs)
        return wrapper
    return decorator


def log_execution(step_name: str = None):
    """
    执行日志装饰器：记录函数开始和结束时间、耗时、入参摘要。
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from config.log_config import logger
            name = step_name or func.__name__
            start = time.time()
            logger.info(f"▶ [{name}] 开始执行, args={args[:3] if args else ''}, kwargs_keys={list(kwargs.keys())}")
            try:
                result = func(*args, **kwargs)
                elapsed = (time.time() - start) * 1000
                logger.info(f"✓ [{name}] 执行完成, 耗时 {elapsed:.0f} ms")
                return result
            except Exception:
                elapsed = (time.time() - start) * 1000
                logger.error(f"✗ [{name}] 执行失败, 耗时 {elapsed:.0f} ms\n{traceback.format_exc()}")
                raise
        return wrapper
    return decorator