"""Project Room API：房间、成员、关联文档、Work Event、Room AI 对话。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_company_with_access, get_current_user
from app.core.database import get_db
from app.models import Company, User
from app.schemas.chat import ChatRequest
from app.schemas.room import (
    RoomCreate,
    RoomDocumentAdd,
    RoomDocumentOut,
    RoomMemberAdd,
    RoomMemberOut,
    RoomOut,
    RoomUpdate,
    WorkEventCreate,
    WorkEventOut,
)
from app.services import agent_service, room_service

router = APIRouter(prefix="/companies/{company_id}/rooms", tags=["rooms"])


async def get_room_of_company(
    room_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    room = room_service.get_room(db, company.id, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目房间不存在")
    return room


def _room_out(room, member_count: int, event_count: int) -> RoomOut:
    out = RoomOut.model_validate(room)
    out.member_count = member_count
    out.event_count = event_count
    return out


# ---------- Room CRUD ----------


@router.get("", response_model=list[RoomOut])
def list_rooms(
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    return [
        _room_out(room, m, e)
        for room, m, e in room_service.list_rooms(db, company.id)
    ]


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    data: RoomCreate,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    room = room_service.create_room(db, company, data, owner_id=current_user.id)
    return _room_out(room, 1, 0)


@router.get("/{room_id}", response_model=RoomOut)
def get_room(
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    members = room_service.list_members(db, room.id)
    events = room_service.list_events(db, room.id, limit=1000)
    return _room_out(room, len(members), len(events))


@router.patch("/{room_id}", response_model=RoomOut)
def update_room(
    data: RoomUpdate,
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    room = room_service.update_room(db, room, data)
    members = room_service.list_members(db, room.id)
    events = room_service.list_events(db, room.id, limit=1000)
    return _room_out(room, len(members), len(events))


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    room_service.delete_room(db, room)


# ---------- 成员 ----------


def _member_out(m) -> RoomMemberOut:
    emp = m.employee
    return RoomMemberOut(
        id=m.id,
        room_id=m.room_id,
        employee_id=m.employee_id,
        role=m.role,
        user_name=emp.user.name if emp and emp.user else None,
        user_email=emp.user.email if emp and emp.user else None,
        position=emp.position if emp else None,
        department_name=emp.department.name if emp and emp.department else None,
        created_at=m.created_at,
    )


@router.get("/{room_id}/members", response_model=list[RoomMemberOut])
def list_members(
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    return [_member_out(m) for m in room_service.list_members(db, room.id)]


@router.post("/{room_id}/members", response_model=RoomMemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    data: RoomMemberAdd,
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        m = room_service.add_member(db, room, data.employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _member_out(m)


@router.delete("/{room_id}/members/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    employee_id: str,
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    room_service.remove_member(db, room, employee_id)


# ---------- 关联文档 ----------


def _doc_out(d) -> RoomDocumentOut:
    return RoomDocumentOut(
        id=d.id,
        room_id=d.room_id,
        document_id=d.document_id,
        document_name=d.document.name if d.document else None,
        document_status=d.document.status.value if d.document and hasattr(d.document.status, "value") else (str(d.document.status) if d.document else None),
        chunk_count=d.document.chunk_count if d.document else None,
        created_at=d.created_at,
    )


@router.get("/{room_id}/documents", response_model=list[RoomDocumentOut])
def list_room_documents(
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    return [_doc_out(d) for d in room_service.list_room_documents(db, room.id)]


@router.post("/{room_id}/documents", response_model=RoomDocumentOut, status_code=status.HTTP_201_CREATED)
def add_room_document(
    data: RoomDocumentAdd,
    room: Annotated[object, Depends(get_room_of_company)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        d = room_service.add_room_document(db, room, data.document_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _doc_out(d)


@router.delete("/{room_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_room_document(
    document_id: str,
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    room_service.remove_room_document(db, room, document_id)


# ---------- Work Event / Timeline ----------


def _event_out(e) -> WorkEventOut:
    return WorkEventOut(
        id=e.id,
        room_id=e.room_id,
        employee_id=e.employee_id,
        type=e.type,
        content=e.content,
        event_date=e.event_date,
        author_name=e.employee.user.name if e.employee and e.employee.user else None,
        author_position=e.employee.position if e.employee else None,
        created_at=e.created_at,
    )


@router.get("/{room_id}/events", response_model=list[WorkEventOut])
def list_events(
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    return [_event_out(e) for e in room_service.list_events(db, room.id)]


@router.post("/{room_id}/events", response_model=WorkEventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    data: WorkEventCreate,
    room: Annotated[object, Depends(get_room_of_company)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    # 以当前用户在企业中的员工身份作为事件作者
    from sqlalchemy import select

    from app.models import Employee

    employee = db.scalar(
        select(Employee).where(
            Employee.company_id == room.company_id, Employee.user_id == current_user.id
        )
    )
    event = room_service.create_event(db, room, data)
    event.employee_id = employee.id if employee else None
    db.commit()
    db.refresh(event)
    return _event_out(event)


@router.delete("/{room_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: str,
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    room_service.delete_event(db, room, event_id)


# ---------- Room AI 对话（自动携带项目上下文） ----------


@router.post("/{room_id}/chat")
async def room_chat(
    data: ChatRequest,
    room: Annotated[object, Depends(get_room_of_company)],
    db: Annotated[Session, Depends(get_db)],
):
    """Room 内 AI 对话：SSE 流式（协议同 assistant chat，含来源）。"""
    room_context = room_service.build_room_context(db, room)
    history = [m.model_dump() for m in data.history]
    generator = agent_service.stream_room_answer(
        company_id=room.company_id,
        room_context=room_context,
        history=history,
        question=data.message,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
