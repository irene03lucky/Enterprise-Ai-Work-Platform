"""Task：项目行动事项（轻量任务）模型。

Task 是 Project Room 内的行动载体，来源有四类：
- MANUAL：人工创建
- CHAT：Project Agent 从对话中识别、经用户确认后创建
- WORK_EVENT：由工作事件派生
- FOLLOW_UP：后续跟进事项（如「上线以后告诉我」）

所有 Task 都保留来源引用（source_event_id / source_quote），便于追溯
「这个任务为什么存在」。

AI 代理边界（本轮）：AI 只能识别与建议 Task，创建与状态变更由人工确认/操作，
AI 不自动替员工做业务决策、不自动对外承诺、不自动修改项目关键状态。
"""

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, OwnershipMixin


class TaskStatus(str, enum.Enum):
    """任务状态（本轮仅三个状态）。"""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class TaskSource(str, enum.Enum):
    """任务来源。"""

    MANUAL = "MANUAL"  # 用户主动创建
    CHAT = "CHAT"  # Project Agent 从对话识别（经确认）
    WORK_EVENT = "WORK_EVENT"  # 由工作事件派生
    FOLLOW_UP = "FOLLOW_UP"  # 后续跟进事项
    AI_TWIN = "AI_TWIN"  # AI 数字分身接收的明确工作要求


class Task(BaseModel, OwnershipMixin):
    """Task：挂在项目房间下的行动事项。"""

    __tablename__ = "tasks"

    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Task 统一在 AI 工作台管理：可属于某个项目，也可以是纯个人/AI 分身事项
    room_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    assignee_employee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employees.id", ondelete="SET NULL"), index=True, nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[TaskStatus] = mapped_column(
        String(20), default=TaskStatus.TODO, nullable=False, index=True
    )
    source: Mapped[TaskSource] = mapped_column(
        String(20), default=TaskSource.MANUAL, nullable=False
    )

    # 来源追溯：关联的工作事件 / 原始对话摘录
    source_event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("work_events.id", ondelete="SET NULL"), nullable=True
    )
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    assignee = relationship("Employee", foreign_keys=[assignee_employee_id])
    room = relationship("Room")
    source_event = relationship("WorkEvent")
    creator = relationship("User", foreign_keys=[created_by])
