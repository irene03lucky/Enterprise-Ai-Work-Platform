"""AI 代处理事项：AI 分身代替本人处理/记录的工作事项。

四类：
- ANSWERED：AI 已回复（普通信息询问，按权限直接回答）
- RECEIVED：AI 已接收（同事/项目侧抛来的工作事项）
- TASK_CREATED：新生成的 Task（明确工作指令 → 自动生成任务）
- NEED_CONFIRM：待本人确认（模糊但必须由本人处理的事项）

工作台前置展示这些事项，让"AI 替我做了什么"可见、可追溯、可接管。
"""

import enum

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AIActivityType(str, enum.Enum):
    ANSWERED = "ANSWERED"
    RECEIVED = "RECEIVED"
    TASK_CREATED = "TASK_CREATED"
    NEED_CONFIRM = "NEED_CONFIRM"


class AIActivity(BaseModel):
    __tablename__ = "ai_activities"

    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 被代理的员工（本人）
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[AIActivityType] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 来源方（如「李四」/「项目：品牌官网升级项目」），用于追溯谁发起
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)

    room_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="SET NULL"), index=True, nullable=True
    )
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    # 待本人确认事项的处理状态
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    employee = relationship("Employee")
    room = relationship("Room")
    task = relationship("Task")
