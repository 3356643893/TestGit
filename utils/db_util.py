from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.db_handler import get_sqlalchemy_url
from models.task_model import Base, TaskStatus, TaskModel

engine = create_engine(get_sqlalchemy_url(), echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db():
    """获取 SQLAlchemy Session 实例（自动选 driver 建 engine）"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_task(task_id: str, task_type: str = "full"):
    """创建一条任务记录"""
    with get_db() as db:
        task = TaskModel(id=task_id, task_type=task_type, status=TaskStatus.PENDING)
        db.add(task)
        return task


def update_task(task_id: str, **kwargs):
    """更新任务状态/结果/耗时"""
    with get_db() as db:
        task = db.query(TaskModel).filter_by(id=task_id).first()
        if task:
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
        return task


def get_task(task_id: str):
    """按 ID 查询任务详情"""
    with get_db() as db:
        return db.query(TaskModel).filter_by(id=task_id).first()


def get_all_tasks(limit: int = 50):
    """查询所有任务列表（按创建时间倒序）"""
    with get_db() as db:
        return db.query(TaskModel).order_by(TaskModel.created_at.desc()).limit(limit).all()