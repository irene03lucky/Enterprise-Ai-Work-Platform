"""Task API：项目任务 CRUD、我的任务、AI 提案确认创建。

权限沿用企业级成员校验（get_company_with_access），
房间级校验复用 rooms.get_room_of_company 的同款逻辑（本轮不做房间级 RBAC）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_company_with_access, get_current_user
from app.core.database import get_db
from app.models import Company, Employee, Room, Task, TaskStatus, User
from app.schemas.task import (
    TaskCreate,
    TaskOut,
    TaskProposalConfirm,
    TaskUpdate,
)
from app.services import room_service, task_service

# 房间级任务
room_router = APIRouter(prefix="/companies/{company_id}/rooms/{room_id}/tasks", tags=["tasks"])
# 企业级任务（我的任务 / 全部）
router = APIRouter(prefix="/companies/{company_id}/tasks", tags=["tasks"])


# ---------- 公共依赖 ----------


def _get_room(
    room_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    room = room_service.get_room(db, company.id, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目房间不存在")
    return room


def _current_employee_id(db: Session, company: Company, user: User) -> str | None:
    employee = db.scalar(
        select(Employee).where(
            Employee.company_id == company.id, Employee.user_id == user.id
        )
    )
    return employee.id if employee else None


def _task_out(task) -> TaskOut:
    return TaskOut(
        id=task.id,
        company_id=task.company_id,
        room_id=task.room_id,
        room_name=task.room.name if task.room else None,
        title=task.title,
        description=task.description,
        assignee_employee_id=task.assignee_employee_id,
        assignee_name=task.assignee.user.name if task.assignee and task.assignee.user else None,
        due_date=task.due_date,
        status=task.status,
        source=task.source,
        source_event_id=task.source_event_id,
        source_quote=task.source_quote,
        created_by=task.created_by,
        creator_name=task.creator.name if task.creator else None,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


# ---------- 房间任务 ----------


@room_router.get("", response_model=list[TaskOut])
def list_room_tasks(
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
    room: Annotated[Room, Depends(_get_room)],
    status: Annotated[TaskStatus | None, Query()] = None,
    assignee_employee_id: Annotated[str | None, Query()] = None,
):
    """房间任务列表（默认按 待办 → 进行中 → 已完成 排序）。"""
    tasks = task_service.list_room_tasks(
        db, room.id, status=status, assignee_employee_id=assignee_employee_id
    )
    return [_task_out(t) for t in tasks]


@room_router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    data: TaskCreate,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    room: Annotated[Room, Depends(_get_room)],
):
    """人工创建任务（source=MANUAL）。"""
    task = task_service.create_task(db, room, data, created_by=current_user.id)
    return _task_out(task)


@room_router.post("/from-proposal", response_model=list[TaskOut], status_code=status.HTTP_201_CREATED)
def create_tasks_from_proposal(
    data: TaskProposalConfirm,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    room: Annotated[Room, Depends(_get_room)],
):
    """把用户确认后的 AI 任务提案创建为 Task（保留来源与原文摘录）。"""
    if not data.proposals:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有待创建的任务提案")
    tasks = task_service.create_from_proposals(db, room, data.proposals, created_by=current_user.id)
    return [_task_out(t) for t in tasks]


@room_router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    data: TaskUpdate,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
    room: Annotated[Room, Depends(_get_room)],
):
    """更新任务：标题/描述/负责人/截止日期/状态（状态变为 DONE 时写入完成时间）。"""
    task = task_service.get_task(db, room.id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return _task_out(task_service.update_task(db, task, data))


@room_router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
    room: Annotated[Room, Depends(_get_room)],
):
    task = task_service.get_task(db, room.id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    task_service.delete_task(db, task)


# ---------- 企业级：我的任务 ----------


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_company_task(
    data: TaskCreate,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """在 AI 工作台创建任务（可关联项目，也可作为个人事项）。"""
    if data.room_id is not None:
        room = room_service.get_room(db, company.id, data.room_id)
        if room is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="关联项目不存在")
    task = task_service.create_company_task(db, company.id, data, created_by=current_user.id)
    return _task_out(task)


@router.patch("/{task_id}", response_model=TaskOut)
def update_company_task(
    task_id: str,
    data: TaskUpdate,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    """工作台内更新任务（标题/描述/负责人/截止/状态）。"""
    task = db.get(Task, task_id)
    if task is None or task.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return _task_out(task_service.update_task(db, task, data))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_task(
    task_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    task = db.get(Task, task_id)
    if task is None or task.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    task_service.delete_task(db, task)


@router.get("", response_model=list[TaskOut])
def list_my_tasks(
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str, Query(pattern="^(my|all|done)$")] = "my",
    status: Annotated[TaskStatus | None, Query()] = None,
    room_id: Annotated[str | None, Query()] = None,
):
    """我的任务（scope=my）/ 全部（all）/ 已完成（done）。"""
    assignee = None
    if scope == "my":
        assignee = _current_employee_id(db, company, current_user)
        if assignee is None:
            return []
    if scope == "done":
        status = status or TaskStatus.DONE
    tasks = task_service.list_company_tasks(
        db,
        company.id,
        assignee_employee_id=assignee,
        status=status,
        room_id=room_id,
    )
    # 「我的任务」默认只展示未完成（已完成在 scope=done 中查看）
    if scope == "my" and status is None:
        tasks = [t for t in tasks if t.status != TaskStatus.DONE]
    return [_task_out(t) for t in tasks]
