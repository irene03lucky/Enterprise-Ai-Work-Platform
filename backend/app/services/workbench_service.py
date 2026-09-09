"""AI 工作台服务层：真人状态、AI 分身、代理权限、AI 代处理事项、今日日程、项目 Update。

工作台只做「聚合与状态维护」，不做业务决策：
- 真人状态/AI 分身状态由用户自己切换；
- AI 只能在已授权范围内代处理事项（判定逻辑见 ai_twin_service）；
- 所有 AI 代处理动作都会落一条 AIActivity，保证可见、可追溯、可接管。
"""

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AIActivity,
    AIActivityType,
    AITwinStatus,
    DEFAULT_DELEGATION_PERMISSIONS,
    Employee,
    EmployeeStatus,
    Room,
    RoomMember,
    RoomStage,
    Schedule,
    Task,
    TaskStatus,
    User,
    WorkEvent,
)
from app.schemas.workbench import (
    AIActivityOut,
    ProjectUpdateCard,
    ScheduleBrief,
    TaskSummary,
    WorkbenchOut,
    WorkbenchProfile,
)

STAGE_LABELS: dict[str, str] = {
    RoomStage.CONTACT.value: "接触",
    RoomStage.NEGOTIATION.value: "洽谈",
    RoomStage.CONTRACT_DRAFT.value: "合同打磨",
    RoomStage.SIGNED.value: "签约",
    RoomStage.DELIVERY.value: "交付",
    RoomStage.ACCEPTANCE.value: "验收",
}

STAGE_ORDER: list[str] = [s.value for s in RoomStage]


def stage_label(stage: str | None) -> str:
    return STAGE_LABELS.get(stage or "", stage or "未设置")


def get_employee(db: Session, company_id: str, user_id: str) -> Employee | None:
    return db.scalar(
        select(Employee).where(
            Employee.company_id == company_id, Employee.user_id == user_id
        )
    )


def build_profile(
    db: Session, company, user: User, employee: Employee | None
) -> WorkbenchProfile:
    # 兼容历史存量数据的 ACTIVE（等价于 ONLINE）
    raw_status = employee.status if employee else EmployeeStatus.ONLINE
    human_status = (
        EmployeeStatus.ONLINE if raw_status == EmployeeStatus.ACTIVE else raw_status
    )
    return WorkbenchProfile(
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
        employee_id=employee.id if employee else None,
        company_id=company.id,
        company_name=company.name,
        department_name=(
            employee.department.name if employee and employee.department else None
        ),
        position=employee.position if employee else None,
        human_status=human_status,
        ai_twin_name=employee.ai_twin_name if employee else None,
        ai_twin_status=employee.ai_twin_status if employee else AITwinStatus.ASSIST,
        ai_permissions=(
            employee.effective_permissions()
            if employee
            else dict(DEFAULT_DELEGATION_PERMISSIONS)
        ),
        ai_twin_display_name=employee.ai_twin_display_name if employee else None,
    )


# ---------- AI 代处理事项 ----------


def _activity_out(a: AIActivity) -> AIActivityOut:
    return AIActivityOut(
        id=a.id,
        company_id=a.company_id,
        employee_id=a.employee_id,
        type=a.type,
        title=a.title,
        content=a.content,
        counterparty=a.counterparty,
        room_id=a.room_id,
        room_name=a.room.name if a.room else None,
        task_id=a.task_id,
        resolved=a.resolved,
        created_at=a.created_at,
    )


def record_activity(
    db: Session,
    company_id: str,
    employee_id: str,
    type: AIActivityType,
    title: str,
    content: str | None = None,
    counterparty: str | None = None,
    room_id: str | None = None,
    task_id: str | None = None,
) -> AIActivity:
    """记录一条 AI 代处理事项（工作台前置展示）。"""
    activity = AIActivity(
        company_id=company_id,
        employee_id=employee_id,
        type=type,
        title=title[:200],
        content=content,
        counterparty=counterparty,
        room_id=room_id,
        task_id=task_id,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def list_ai_items(
    db: Session, company_id: str, employee_id: str, limit: int = 30
) -> list[AIActivityOut]:
    rows = list(
        db.scalars(
            select(AIActivity)
            .where(
                AIActivity.company_id == company_id,
                AIActivity.employee_id == employee_id,
            )
            .options(selectinload(AIActivity.room))
            .order_by(AIActivity.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [_activity_out(a) for a in rows]


def resolve_activity(
    db: Session, activity_id: str, employee_id: str, resolved: bool = True
) -> AIActivity | None:
    activity = db.get(AIActivity, activity_id)
    if activity is None or activity.employee_id != employee_id:
        return None
    activity.resolved = resolved
    db.commit()
    db.refresh(activity)
    return activity


# ---------- 今日日程 ----------


def list_schedules_by_day(
    db: Session, company_id: str, user_id: str, day: date
) -> list[ScheduleBrief]:
    rows = list(
        db.scalars(
            select(Schedule)
            .where(Schedule.company_id == company_id, Schedule.user_id == user_id)
            .options(selectinload(Schedule.room))
            .order_by(Schedule.start_time)
        ).all()
    )
    out: list[ScheduleBrief] = []
    for s in rows:
        local_day = s.start_time.astimezone().date() if s.start_time.tzinfo else s.start_time.date()
        if local_day != day:
            continue
        out.append(
            ScheduleBrief(
                id=s.id,
                title=s.title,
                start_time=s.start_time,
                end_time=s.end_time,
                room_id=s.room_id,
                room_name=s.room.name if s.room else None,
                note=s.note,
            )
        )
    return out


# ---------- 我参与项目的最新 Update ----------


def list_project_updates(
    db: Session, company_id: str, employee_id: str, limit: int = 6
) -> list[ProjectUpdateCard]:
    room_ids = list(
        db.scalars(
            select(RoomMember.room_id).where(RoomMember.employee_id == employee_id)
        ).all()
    )
    if not room_ids:
        # 未加入任何项目时，展示企业内最近活跃的项目（只读概览）
        room_ids = list(
            db.scalars(
                select(Room.id)
                .where(Room.company_id == company_id)
                .order_by(Room.created_at.desc())
                .limit(limit)
            ).all()
        )
    if not room_ids:
        return []

    rooms = list(
        db.scalars(
            select(Room)
            .where(Room.id.in_(room_ids))
            .order_by(Room.created_at.desc())
            .limit(limit)
        ).all()
    )
    open_counts = dict(
        db.execute(
            select(Task.room_id, func.count(Task.id))
            .where(
                Task.room_id.in_(room_ids),
                Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
            )
            .group_by(Task.room_id)
        ).all()
    )

    cards: list[ProjectUpdateCard] = []
    for room in rooms:
        latest = db.scalar(
            select(WorkEvent)
            .where(WorkEvent.room_id == room.id)
            .options(selectinload(WorkEvent.employee).selectinload(Employee.user))
            .order_by(WorkEvent.event_date.desc(), WorkEvent.created_at.desc())
        )
        stage_value = room.stage.value if hasattr(room.stage, "value") else str(room.stage)
        cards.append(
            ProjectUpdateCard(
                room_id=room.id,
                room_name=room.name,
                stage=stage_value,
                stage_label=stage_label(stage_value),
                status=(
                    room.status.value if hasattr(room.status, "value") else str(room.status)
                ),
                latest_event_id=latest.id if latest else None,
                latest_event_type=(
                    latest.type.value if latest and hasattr(latest.type, "value") else None
                ),
                latest_event_content=latest.content[:200] if latest else None,
                latest_event_author=(
                    latest.employee.user.name
                    if latest and latest.employee and latest.employee.user
                    else None
                ),
                latest_event_at=latest.event_date if latest else None,
                open_task_count=open_counts.get(room.id, 0),
            )
        )
    return cards


def task_summary(db: Session, company_id: str, employee_id: str) -> TaskSummary:
    rows = dict(
        db.execute(
            select(Task.status, func.count(Task.id))
            .where(Task.company_id == company_id, Task.assignee_employee_id == employee_id)
            .group_by(Task.status)
        ).all()
    )
    today = date.today()
    overdue = db.scalar(
        select(func.count(Task.id)).where(
            Task.company_id == company_id,
            Task.assignee_employee_id == employee_id,
            Task.status != TaskStatus.DONE,
            Task.due_date.is_not(None),
            Task.due_date < today,
        )
    )
    return TaskSummary(
        todo=rows.get(TaskStatus.TODO, 0),
        in_progress=rows.get(TaskStatus.IN_PROGRESS, 0),
        done=rows.get(TaskStatus.DONE, 0),
        overdue=overdue or 0,
    )


def build_workbench(
    db: Session, company, user: User, employee: Employee | None, today: date | None = None
) -> WorkbenchOut:
    today = today or datetime.now(timezone.utc).astimezone().date()
    if employee is None:
        return WorkbenchOut(
            profile=build_profile(db, company, user, None),
            today=today,
        )
    return WorkbenchOut(
        profile=build_profile(db, company, user, employee),
        ai_items=list_ai_items(db, company.id, employee.id),
        today_schedules=list_schedules_by_day(db, company.id, user.id, today),
        project_updates=list_project_updates(db, company.id, employee.id),
        task_summary=task_summary(db, company.id, employee.id),
        today=today,
    )
