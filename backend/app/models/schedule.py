"""日程（Calendar）：帮助 AI 理解用户未来安排与真人状态的轻量结构。

第一版只支持：标题 / 时间 / 关联 Room / 备注；
visibility 仅预留（PRIVATE / COMPANY），暂不做私人与公司日程的分类运营。
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, OwnershipMixin


class ScheduleVisibility(str, enum.Enum):
    PRIVATE = "PRIVATE"
    COMPANY = "COMPANY"


class Schedule(BaseModel, OwnershipMixin):
    __tablename__ = "schedules"

    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    room_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="SET NULL"), index=True, nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[ScheduleVisibility] = mapped_column(
        String(20), default=ScheduleVisibility.PRIVATE, nullable=False
    )

    room = relationship("Room")
