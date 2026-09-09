"""最近对话服务层。

定位：这是「会话记录」，用于回到刚才的上下文（知识查询 / 项目问答 / 文件分析 / 普通对话），
**不是 AI 长期记忆**，不参与知识库检索，也不作为企业记忆使用。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Conversation, ConversationMessage, ConversationKind, Room
from app.schemas.conversation import ConversationCreate


def list_conversations(
    db: Session, company_id: str, user_id: str, limit: int = 8
) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(
                Conversation.company_id == company_id,
                Conversation.user_id == user_id,
            )
            .options(selectinload(Conversation.room))
            .order_by(Conversation.last_message_at.desc())
            .limit(limit)
        ).all()
    )


def get_conversation(
    db: Session, conversation_id: str, user_id: str
) -> Conversation | None:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        return None
    return conversation


def create_conversation(
    db: Session, company_id: str, user_id: str, data: ConversationCreate
) -> Conversation:
    conversation = Conversation(
        company_id=company_id,
        user_id=user_id,
        title=data.title[:200],
        kind=data.kind,
        room_id=data.room_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def append_message(
    db: Session, conversation: Conversation, role: str, content: str
) -> ConversationMessage:
    message = ConversationMessage(
        conversation_id=conversation.id,
        role=role,
        content=content[:8000],
    )
    conversation.last_message = content[:500]
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def ensure_conversation(
    db: Session,
    company_id: str,
    user_id: str,
    conversation_id: str | None,
    kind: ConversationKind,
    room_id: str | None,
    title: str,
) -> Conversation:
    """复用指定会话，或按标题新建一条（同一天内同标题会新建，保持实现简单）。"""
    if conversation_id:
        existing = get_conversation(db, conversation_id, user_id)
        if existing is not None:
            if room_id and not existing.room_id:
                existing.room_id = room_id
            db.commit()
            return existing
    return create_conversation(
        db,
        company_id,
        user_id,
        ConversationCreate(title=title[:60], kind=kind, room_id=room_id),
    )


def delete_conversation(db: Session, conversation: Conversation) -> None:
    db.delete(conversation)
    db.commit()


def room_name_of(db: Session, room_id: str | None) -> str | None:
    if not room_id:
        return None
    room = db.get(Room, room_id)
    return room.name if room else None
