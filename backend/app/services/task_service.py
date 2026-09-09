"""Task 服务层：任务 CRUD、我的任务、按来源追溯、AI 提案落库。

设计要点：
- 任务挂在项目房间（Room）下，同时冗余 company_id 便于企业级查询；
- 状态流转为 TODO → IN_PROGRESS → DONE，标记 DONE 时写入 completed_at；
- AI 提案（TaskProposal）统一经 create_from_proposals 落库，
  保留 source / source_quote / source_event_id，便于追溯任务来源；
- 负责人支持按姓名模糊匹配（AI 只能给出「李四」这类名字）。
"""

from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Employee,
    EventVisibility,
    Room,
    Task,
    TaskSource,
    TaskStatus,
    User,
    WorkEvent,
    WorkEventType,
)
from app.schemas.task import TaskCreate, TaskProposal, TaskUpdate

# 便于前端/提示词复用的排序权重
STATUS_ORDER = {TaskStatus.TODO: 0, TaskStatus.IN_PROGRESS: 1, TaskStatus.DONE: 2}


# ---------- 查询 ----------


def _task_query(db: Session):
    return (
        select(Task)
        .options(
            selectinload(Task.assignee).selectinload(Employee.user),
            selectinload(Task.creator),
            selectinload(Task.room),
        )
        .order_by(Task.created_at.desc())
    )


def list_room_tasks(
    db: Session,
    room_id: str,
    status: TaskStatus | None = None,
    assignee_employee_id: str | None = None,
) -> list[Task]:
    stmt = _task_query(db).where(Task.room_id == room_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if assignee_employee_id:
        stmt = stmt.where(Task.assignee_employee_id == assignee_employee_id)
    tasks = list(db.scalars(stmt).all())
    return sorted(tasks, key=lambda t: (STATUS_ORDER.get(t.status, 9), t.created_at))


def list_company_tasks(
    db: Session,
    company_id: str,
    assignee_employee_id: str | None = None,
    status: TaskStatus | None = None,
    room_id: str | None = None,
) -> list[Task]:
    stmt = _task_query(db).where(Task.company_id == company_id)
    if assignee_employee_id:
        stmt = stmt.where(Task.assignee_employee_id == assignee_employee_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if room_id:
        stmt = stmt.where(Task.room_id == room_id)
    tasks = list(db.scalars(stmt).all())
    return sorted(tasks, key=lambda t: (STATUS_ORDER.get(t.status, 9), t.created_at))


def get_task(db: Session, room_id: str, task_id: str) -> Task | None:
    task = db.get(Task, task_id)
    if task is None or task.room_id != room_id:
        return None
    return task


def count_open_tasks(db: Session, room_ids: list[str]) -> dict[str, int]:
    """批量统计房间的未完成任务数（TODO + IN_PROGRESS）。"""
    if not room_ids:
        return {}
    rows = db.execute(
        select(Task.room_id, func.count(Task.id))
        .where(
            Task.room_id.in_(room_ids),
            Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
        )
        .group_by(Task.room_id)
    ).all()
    return dict(rows)


def summarize_room_tasks(db: Session, room_id: str) -> dict:
    """房间任务概览：各状态数量 + 逾期数量。"""
    rows = dict(
        db.execute(
            select(Task.status, func.count(Task.id))
            .where(Task.room_id == room_id)
            .group_by(Task.status)
        ).all()
    )
    today = date.today()
    overdue = db.scalar(
        select(func.count(Task.id)).where(
            Task.room_id == room_id,
            Task.status != TaskStatus.DONE,
            Task.due_date.is_not(None),
            Task.due_date < today,
        )
    )
    return {
        "todo": rows.get(TaskStatus.TODO, 0),
        "in_progress": rows.get(TaskStatus.IN_PROGRESS, 0),
        "done": rows.get(TaskStatus.DONE, 0),
        "overdue": overdue or 0,
    }


# ---------- 写入 ----------


def create_task(
    db: Session,
    room: Room,
    data: TaskCreate,
    created_by: str | None = None,
    source: TaskSource = TaskSource.MANUAL,
    source_event_id: str | None = None,
    source_quote: str | None = None,
) -> Task:
    """在项目房间下创建任务（房间级入口）。"""
    return create_company_task(
        db,
        company_id=room.company_id,
        data=data.model_copy(update={"room_id": room.id}),
        created_by=created_by,
        source=source,
        source_event_id=source_event_id,
        source_quote=source_quote,
    )


def create_company_task(
    db: Session,
    company_id: str,
    data: TaskCreate,
    created_by: str | None = None,
    source: TaskSource = TaskSource.MANUAL,
    source_event_id: str | None = None,
    source_quote: str | None = None,
) -> Task:
    """企业级创建任务：可属于某个 Room，也可以是纯个人/AI 分身事项。"""
    task = Task(
        company_id=company_id,
        room_id=data.room_id,
        title=data.title,
        description=data.description,
        assignee_employee_id=data.assignee_employee_id,
        due_date=data.due_date,
        status=data.status,
        source=source,
        source_event_id=source_event_id,
        source_quote=source_quote,
        created_by=created_by,
        owner_id=created_by,
        completed_at=datetime.now(timezone.utc) if data.status == TaskStatus.DONE else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task: Task, data: TaskUpdate) -> Task:
    prev_status = task.status
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(task, field, value)
    if "status" in payload:
        if task.status == TaskStatus.DONE:
            task.completed_at = task.completed_at or datetime.now(timezone.utc)
        else:
            task.completed_at = None
    db.commit()
    db.refresh(task)

    # 任务完成 → 自动形成项目 Update（T04.7 状态同步闭环）
    if (
        task.room_id
        and prev_status != TaskStatus.DONE
        and task.status == TaskStatus.DONE
    ):
        assignee_name = (
            task.assignee.user.name if task.assignee and task.assignee.user else None
        )
        db.add(
            WorkEvent(
                room_id=task.room_id,
                employee_id=task.assignee_employee_id,
                type=WorkEventType.TASK_UPDATE,
                visibility=EventVisibility.PUBLIC,
                content=(
                    f"任务完成：{task.title}"
                    f"｜负责人：{assignee_name or '未分配'}｜状态：已完成"
                ),
            )
        )
        db.commit()
    return task


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()


# ---------- AI 提案 → Task ----------


def resolve_employee_by_name(db: Session, company_id: str, name: str | None) -> Employee | None:
    """按姓名（可能带空格/职位后缀）解析企业内员工。"""
    if not name:
        return None
    keyword = name.strip()
    if not keyword:
        return None
    employee = db.scalar(
        select(Employee)
        .join(User, User.id == Employee.user_id)
        .where(Employee.company_id == company_id, User.name == keyword)
    )
    if employee is None:
        # 退化为包含匹配（如「李四同学」「李四（设计）」）
        employee = db.scalar(
            select(Employee)
            .join(User, User.id == Employee.user_id)
            .where(
                Employee.company_id == company_id,
                or_(User.name.like(f"%{keyword}%"), User.email.like(f"%{keyword}%")),
            )
        )
    return employee


def create_from_proposals(
    db: Session,
    room: Room,
    proposals: list[TaskProposal],
    created_by: str | None = None,
) -> list[Task]:
    """把用户确认后的 AI 提案批量落库为 Task。"""
    created: list[Task] = []
    for proposal in proposals:
        assignee_id = proposal.assignee_employee_id
        if assignee_id is None and proposal.assignee_name:
            employee = resolve_employee_by_name(db, room.company_id, proposal.assignee_name)
            assignee_id = employee.id if employee else None
        task = Task(
            company_id=room.company_id,
            room_id=room.id,
            title=proposal.title,
            description=proposal.description,
            assignee_employee_id=assignee_id,
            due_date=proposal.due_date,
            status=TaskStatus.TODO,
            source=proposal.source,
            source_event_id=proposal.source_event_id,
            source_quote=proposal.source_quote,
            created_by=created_by,
            owner_id=created_by,
        )
        db.add(task)
        created.append(task)
    if created:
        db.commit()
        for task in created:
            db.refresh(task)
    return created
