"""Project Room 与 Work Event 模型。

Room 是项目工作空间：聚合成员、关联知识文档、工作事件与 Timeline。
Work Event 是员工工作过程的轻量记录，供 AI 理解「项目正在发生什么」。
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, OwnershipMixin


class RoomStatus(str, Enum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class RoomStage(str, Enum):
    """项目阶段：接触 → 洽谈 → 合同打磨 → 签约 → 交付 → 验收。

    阶段是项目对外的「大进度」，相关部门也能看到；
    详细进展、风险与内部 Work Event 只对项目成员/管理层开放。
    """

    CONTACT = "CONTACT"
    NEGOTIATION = "NEGOTIATION"
    CONTRACT_DRAFT = "CONTRACT_DRAFT"
    SIGNED = "SIGNED"
    DELIVERY = "DELIVERY"
    ACCEPTANCE = "ACCEPTANCE"


class EventVisibility(str, Enum):
    """工作事件可见范围。

    PUBLIC：公开里程碑（相关部门可见）
    INTERNAL：内部事件（仅项目成员 / 管理层可见）
    """

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"


class WorkEventType(str, Enum):
    MEETING = "meeting"
    WORK_LOG = "work_log"
    CUSTOMER_FEEDBACK = "customer_feedback"
    DECISION = "decision"
    TASK_UPDATE = "task_update"
    DOCUMENT_UPDATE = "document_update"


class Room(BaseModel, OwnershipMixin):
    """Project Room：项目工作空间。"""

    __tablename__ = "rooms"

    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RoomStatus] = mapped_column(
        String(20), default=RoomStatus.ACTIVE, nullable=False
    )
    # 项目阶段（对相关部门也可见的「大进度」）
    stage: Mapped[RoomStage] = mapped_column(
        String(20), default=RoomStage.CONTACT, nullable=False
    )
    stage_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    members = relationship("RoomMember", back_populates="room", cascade="all, delete-orphan")
    documents = relationship("RoomDocument", back_populates="room", cascade="all, delete-orphan")
    events = relationship(
        "WorkEvent", back_populates="room", cascade="all, delete-orphan"
    )


class RoomMember(BaseModel):
    """房间成员（企业员工维度）。"""

    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "employee_id", name="uq_room_member"),)

    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # OWNER / MEMBER（预留，本轮不实现房间级权限）
    role: Mapped[str] = mapped_column(String(20), default="MEMBER", nullable=False)

    room = relationship("Room", back_populates="members")
    employee = relationship("Employee")


class RoomDocument(BaseModel):
    """房间关联的知识文档（复用 Knowledge 模块，不新建文档体系）。"""

    __tablename__ = "room_documents"
    __table_args__ = (UniqueConstraint("room_id", "document_id", name="uq_room_document"),)

    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    added_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    room = relationship("Room", back_populates="documents")
    document = relationship("KnowledgeDocument")


class WorkEvent(BaseModel):
    """工作事件：项目过程记录，构成 Timeline。"""

    __tablename__ = "work_events"

    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    employee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[WorkEventType] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # PUBLIC=公开里程碑（相关部门可见）；INTERNAL=内部事件（仅项目成员/管理层）
    visibility: Mapped[EventVisibility] = mapped_column(
        String(20), default=EventVisibility.INTERNAL, nullable=False
    )
    event_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    room = relationship("Room", back_populates="events")
    employee = relationship("Employee")
