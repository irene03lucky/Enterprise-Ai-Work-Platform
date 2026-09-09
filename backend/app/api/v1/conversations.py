"""最近对话 API：知识查询 / 项目问答 / 文件分析 / 普通 AI 工作对话。

注意：这是会话记录，用于回到刚才的上下文，不等同于 AI 长期记忆。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_company_with_access, get_current_user
from app.core.database import get_db
from app.models import Company, User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
)
from app.services import conversation_service

router = APIRouter(prefix="/companies/{company_id}/conversations", tags=["conversations"])


def _out(c) -> ConversationOut:
    return ConversationOut(
        id=c.id,
        company_id=c.company_id,
        user_id=c.user_id,
        title=c.title,
        kind=c.kind,
        room_id=c.room_id,
        room_name=c.room.name if c.room else None,
        last_message=c.last_message,
        last_message_at=c.last_message_at,
        created_at=c.created_at,
    )


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 8,
):
    return [
        _out(c)
        for c in conversation_service.list_conversations(
            db, company.id, current_user.id, limit=limit
        )
    ]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    data: ConversationCreate,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _out(conversation_service.create_conversation(db, company.id, current_user.id, data))


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    conversation = conversation_service.get_conversation(db, conversation_id, current_user.id)
    if conversation is None or conversation.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    return ConversationDetailOut(
        **_out(conversation).model_dump(),
        messages=[
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at,
            }
            for m in conversation.messages
        ],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    conversation = conversation_service.get_conversation(db, conversation_id, current_user.id)
    if conversation is None or conversation.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    conversation_service.delete_conversation(db, conversation)
