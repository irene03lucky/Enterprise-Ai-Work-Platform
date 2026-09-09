"""Project Room 服务层：房间、成员、关联文档、Work Event、项目上下文构建。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Company,
    Employee,
    EventVisibility,
    KnowledgeDocument,
    Room,
    RoomDocument,
    RoomMember,
    RoomStage,
    RoomStatus,
    WorkEvent,
)
from app.schemas.room import RoomCreate, RoomUpdate, WorkEventCreate

# 访问深度：member=项目成员/管理层（全量）| related=普通相关部门（阶段 + 公开里程碑）
ACCESS_MEMBER = "member"
ACCESS_RELATED = "related"


# ---------- Room CRUD ----------


def list_rooms(db: Session, company_id: str) -> list[tuple[Room, int, int]]:
    """返回 (房间, 成员数, 事件数) 列表。"""
    rooms = list(
        db.scalars(
            select(Room).where(Room.company_id == company_id).order_by(Room.created_at)
        ).all()
    )
    if not rooms:
        return []
    ids = [r.id for r in rooms]
    member_counts = dict(
        db.execute(
            select(RoomMember.room_id, func.count(RoomMember.id))
            .where(RoomMember.room_id.in_(ids))
            .group_by(RoomMember.room_id)
        ).all()
    )
    event_counts = dict(
        db.execute(
            select(WorkEvent.room_id, func.count(WorkEvent.id))
            .where(WorkEvent.room_id.in_(ids))
            .group_by(WorkEvent.room_id)
        ).all()
    )
    return [(r, member_counts.get(r.id, 0), event_counts.get(r.id, 0)) for r in rooms]


def get_room(db: Session, company_id: str, room_id: str) -> Room | None:
    room = db.get(Room, room_id)
    if room is None or room.company_id != company_id:
        return None
    return room


def create_room(db: Session, company: Company, data: RoomCreate, owner_id: str | None) -> Room:
    room = Room(
        company_id=company.id,
        name=data.name,
        description=data.description,
        status=data.status,
        stage=data.stage,
        owner_id=owner_id,
    )
    db.add(room)
    db.flush()
    # 创建者（管理员）自动成为 OWNER 成员
    if owner_id:
        employee = db.scalar(
            select(Employee).where(
                Employee.company_id == company.id, Employee.user_id == owner_id
            )
        )
        if employee:
            db.add(RoomMember(room_id=room.id, employee_id=employee.id, role="OWNER"))
    db.commit()
    db.refresh(room)
    return room


def update_room(db: Session, room: Room, data: RoomUpdate) -> Room:
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(room, field, value)
    if "stage" in payload:
        from datetime import datetime, timezone

        room.stage_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(room)
    return room


# ---------- 访问深度（不同角色看到不同深度） ----------


def get_access_level(db: Session, room: Room, user_id: str | None) -> str:
    """判断访问者可见深度。

    - member：项目成员 / 企业所有者（管理层）→ 详细进展、风险、内部 Work Event
    - related：其他企业内部成员（含相关部门）→ 项目大阶段 + 公开里程碑
    """
    if user_id is None:
        return ACCESS_RELATED
    if room.owner_id == user_id:
        return ACCESS_MEMBER
    is_member = db.scalar(
        select(RoomMember.id).where(
            RoomMember.room_id == room.id,
            RoomMember.employee_id.in_(
                select(Employee.id).where(
                    Employee.company_id == room.company_id, Employee.user_id == user_id
                )
            ),
        )
    )
    if is_member is not None:
        return ACCESS_MEMBER
    return ACCESS_RELATED


def delete_room(db: Session, room: Room) -> None:
    db.delete(room)  # 成员/文档关联/事件级联删除
    db.commit()


# ---------- 成员 ----------


def list_members(db: Session, room_id: str) -> list[RoomMember]:
    return list(
        db.scalars(
            select(RoomMember)
            .where(RoomMember.room_id == room_id)
            .options(selectinload(RoomMember.employee).selectinload(Employee.user))
            .order_by(RoomMember.created_at)
        ).all()
    )


def add_member(db: Session, room: Room, employee_id: str) -> RoomMember:
    employee = db.get(Employee, employee_id)
    if employee is None or employee.company_id != room.company_id:
        raise ValueError("员工不存在或不属于该企业")
    existing = db.scalar(
        select(RoomMember).where(
            RoomMember.room_id == room.id, RoomMember.employee_id == employee_id
        )
    )
    if existing:
        return existing
    member = RoomMember(room_id=room.id, employee_id=employee_id)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, room: Room, employee_id: str) -> None:
    member = db.scalar(
        select(RoomMember).where(
            RoomMember.room_id == room.id, RoomMember.employee_id == employee_id
        )
    )
    if member is not None:
        db.delete(member)
        db.commit()


# ---------- 关联文档（复用 Knowledge） ----------


def list_room_documents(db: Session, room_id: str) -> list[RoomDocument]:
    return list(
        db.scalars(
            select(RoomDocument)
            .where(RoomDocument.room_id == room_id)
            .options(selectinload(RoomDocument.document))
            .order_by(RoomDocument.created_at)
        ).all()
    )


def add_room_document(
    db: Session, room: Room, document_id: str, added_by: str | None
) -> RoomDocument:
    doc = db.get(KnowledgeDocument, document_id)
    if doc is None or doc.company_id != room.company_id:
        raise ValueError("文档不存在或不属于该企业")
    existing = db.scalar(
        select(RoomDocument).where(
            RoomDocument.room_id == room.id, RoomDocument.document_id == document_id
        )
    )
    if existing:
        return existing
    link = RoomDocument(room_id=room.id, document_id=document_id, added_by=added_by)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def remove_room_document(db: Session, room: Room, document_id: str) -> None:
    link = db.scalar(
        select(RoomDocument).where(
            RoomDocument.room_id == room.id, RoomDocument.document_id == document_id
        )
    )
    if link is not None:
        db.delete(link)
        db.commit()


# ---------- Work Event / Timeline ----------


def list_events(
    db: Session, room_id: str, limit: int = 200, access_level: str = ACCESS_MEMBER
) -> list[WorkEvent]:
    """Timeline：事件按时间倒序。

    access_level=related 时只返回公开里程碑，内部 Work Event 不可见。
    """
    stmt = (
        select(WorkEvent)
        .where(WorkEvent.room_id == room_id)
        .options(selectinload(WorkEvent.employee).selectinload(Employee.user))
    )
    if access_level != ACCESS_MEMBER:
        stmt = stmt.where(WorkEvent.visibility == EventVisibility.PUBLIC)
    stmt = stmt.order_by(WorkEvent.event_date.desc(), WorkEvent.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def create_event(db: Session, room: Room, data: WorkEventCreate) -> WorkEvent:
    event = WorkEvent(
        room_id=room.id,
        type=data.type,
        content=data.content,
        visibility=data.visibility,
        event_date=data.event_date or None,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, room: Room, event_id: str) -> None:
    event = db.get(WorkEvent, event_id)
    if event is not None and event.room_id == room.id:
        db.delete(event)
        db.commit()


# ---------- 项目上下文（供 Room AI 使用） ----------


def build_room_context(
    db: Session, room: Room, recent_limit: int = 20, access_level: str = ACCESS_MEMBER
) -> dict:
    """汇总项目基本信息、阶段、成员、关联文档、最近事件（Timeline 摘要）。"""
    members = list_members(db, room.id)
    documents = list_room_documents(db, room.id)
    events = list_events(db, room.id, limit=recent_limit, access_level=access_level)

    member_lines = []
    for m in members:
        emp = m.employee
        if emp is None:
            continue
        dept = emp.department.name if emp.department else "未分配部门"
        member_lines.append(
            f"- {emp.user.name if emp.user else '未知'}（{dept}"
            + (f"·{emp.position}" if emp.position else "")
            + (f"，房间角色:{m.role}" if m.role == "OWNER" else "")
            + "）"
        )

    doc_lines = [f"- {d.document.name}（{d.document.chunk_count}个知识块）" for d in documents if d.document]

    event_lines = []
    for e in reversed(events):  # 时间正序便于阅读
        author = e.employee.user.name if e.employee and e.employee.user else "未知"
        date = e.event_date.strftime("%Y-%m-%d %H:%M") if e.event_date else ""
        etype = e.type.value if hasattr(e.type, "value") else str(e.type)
        event_lines.append(f"[{date}][{etype}] {author}: {e.content[:400]}")

    stage_value = room.stage.value if isinstance(room.stage, RoomStage) else str(room.stage)
    return {
        "room_id": room.id,
        "name": room.name,
        "status": room.status.value if isinstance(room.status, RoomStatus) else str(room.status),
        "stage": stage_value,
        "stage_label": stage_value,
        "access_level": access_level,
        "description": room.description,
        "members": member_lines,
        "documents": doc_lines,
        "document_ids": [d.document_id for d in documents],
        "recent_events": event_lines,
    }
