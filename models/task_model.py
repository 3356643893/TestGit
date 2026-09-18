from enum import Enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TaskModel(Base):
    __tablename__ = "scheduler_tasks"

    id = Column(String(64), primary_key=True)
    task_type = Column(String(32), default="full")
    status = Column(String(16), default=TaskStatus.PENDING)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)