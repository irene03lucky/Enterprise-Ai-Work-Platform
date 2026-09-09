"""Room 项目聊天 API：成员沟通上下文 + AI 分身接管（项目群公开可见）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_company_with_access, get_current_user
from app.core.database import get_db
from app.models import Company, Employee, User
from app.schemas.room import RoomChatMessageCreate, RoomChatMessageOut
from app.services import room_chat_service
from app.models import Room

router = APIRouter(prefix="/companies/{company_id}/rooms", tags=["room-chat"])


def _get_room(
    room_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
) -> Room:
    from app.services import room_service

    room = room_service.get_room(db, company.id, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目房间不存在")
    return room


def _msg_out(m) -> RoomChatMessageOut:
    return RoomChatMessageOut(
        id=m.id,
        room_id=m.room_id,
        employee_id=m.employee_id,
        sender_kind=m.sender_kind,
        sender_name=room_chat_service._sender_name(m),  # noqa: SLF001 - 模块内序列化辅助
        content=m.content,
        created_at=m.created_at,
    )


@router.get("/{room_id}/chat", response_model=list[RoomChatMessageOut])
def list_chat(
    room: Annotated[Room, Depends(_get_room)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """项目聊天记录（项目成员公开可见；系统提示含 AI 接管状态）。"""
    return [_msg_out(m) for m in room_chat_service.list_messages(db, room.id)]


@router.post("/{room_id}/chat", response_model=list[RoomChatMessageOut])
async def send_chat(
    data: RoomChatMessageCreate,
    room: Annotated[Room, Depends(_get_room)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """发送项目聊天消息。若点名的成员满足接管条件，其 AI 分身会在授权范围内接管回复，
    并可能生成个人 Task 与项目 Update（同步 Timeline）。返回本次新增的全部消息。"""
    employee = db.scalar(
        select(Employee).where(
            Employee.company_id == room.company_id, Employee.user_id == current_user.id
        )
    )
    created = await room_chat_service.send_message(db, room, employee, data.content)
    return [_msg_out(m) for m in created]
