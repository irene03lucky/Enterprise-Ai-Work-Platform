"""最近对话 Schema。

注意：这是会话记录（便于回到刚才的上下文），不是 AI 长期记忆。
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.conversation import ConversationKind


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: ConversationKind = ConversationKind.GENERAL
    room_id: str | None = None


class ConversationOut(BaseModel):
    id: str
    company_id: str
    user_id: str
    title: str
    kind: ConversationKind
    room_id: str | None = None
    room_name: str | None = None
    last_message: str | None = None
    last_message_at: datetime
    created_at: datetime


class ConversationMessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime


class ConversationDetailOut(ConversationOut):
    messages: list[ConversationMessageOut] = Field(default_factory=list)
