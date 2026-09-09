"""Room 项目聊天：项目成员围绕项目沟通的上下文空间。

定位：不是即时通讯工具，而是「项目事实」的一部分——
聊天内容会被 AI 理解，并在授权情况下由成员的 AI 分身接管回复，
进而生成 Task 与项目 Update（业务闭环）。

sender_kind：
- USER：成员本人发言（employee_id = 发言成员）；
- AI：成员的 AI 分身接管回复（employee_id = 被代理成员）；
- SYSTEM：系统提示（如「张三「会议中」 张三·AI 已接管当前聊天」），employee_id 为空。
"""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class RoomChatMessage(BaseModel):
    __tablename__ = "room_chat_messages"

    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # USER/AI 消息指向对应成员（AI 消息 = 被代理成员）；SYSTEM 为空
    employee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employees.id", ondelete="SET NULL"), index=True, nullable=True
    )
    sender_kind: Mapped[str] = mapped_column(String(10), default="USER", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    employee = relationship("Employee")
