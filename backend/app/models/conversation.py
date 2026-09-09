"""最近对话：知识查询 / 项目问答 / 文件分析 / 普通 AI 工作对话的记录。

设计边界：这只是「最近对话」的会话记录，用于快速回到刚才的上下文，
**不等同于 AI 长期记忆**，也不作为企业记忆或知识资产使用。
"""

import enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ConversationKind(str, enum.Enum):
    KNOWLEDGE = "KNOWLEDGE"  # 企业知识查询
    PROJECT = "PROJECT"  # 项目问答（Project Agent）
    FILE = "FILE"  # 文件分析
    GENERAL = "GENERAL"  # 普通 AI 工作对话


class Conversation(BaseModel):
    __tablename__ = "conversations"

    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[ConversationKind] = mapped_column(
        String(20), default=ConversationKind.GENERAL, nullable=False
    )
    room_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # 列表展示用的最后一条摘要
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )
    room = relationship("Room")


class ConversationMessage(BaseModel):
    __tablename__ = "conversation_messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
