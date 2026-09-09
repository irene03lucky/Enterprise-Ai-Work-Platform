"""Calendar API：轻量日程（标题 / 时间 / 关联 Room / 备注，visibility 仅预留）。"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_company_with_access, get_current_user
from app.core.database import get_db
from app.models import Company, Schedule, User
from app.schemas.schedule import ScheduleCreate, ScheduleOut, ScheduleUpdate
from app.services import schedule_service

router = APIRouter(prefix="/companies/{company_id}/schedules", tags=["calendar"])


def _schedule_out(s: Schedule) -> ScheduleOut:
    return ScheduleOut(
        id=s.id,
        company_id=s.company_id,
        user_id=s.user_id,
        title=s.title,
        start_time=s.start_time,
        end_time=s.end_time,
        room_id=s.room_id,
        room_name=s.room.name if s.room else None,
        note=s.note,
        visibility=s.visibility,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("", response_model=list[ScheduleOut])
def list_schedules(
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    day: Annotated[date | None, Query()] = None,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
):
    """日程列表：默认今天；也可指定 day 或 start/end 区间。"""
    schedules = schedule_service.list_schedules(
        db, company.id, current_user.id, day=day, start=start, end=end
    )
    return [_schedule_out(s) for s in schedules]


@router.post("", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule(
    data: ScheduleCreate,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """创建日程：帮助 AI 理解你的未来安排与真人状态。"""
    if data.room_id is not None:
        from app.services import room_service

        room = room_service.get_room(db, company.id, data.room_id)
        if room is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="关联项目不存在")
    schedule = schedule_service.create_schedule(db, company.id, current_user.id, data)
    return _schedule_out(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: str,
    data: ScheduleUpdate,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    schedule = schedule_service.get_schedule(db, schedule_id, current_user.id)
    if schedule is None or schedule.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日程不存在")
    return _schedule_out(schedule_service.update_schedule(db, schedule, data))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    schedule = schedule_service.get_schedule(db, schedule_id, current_user.id)
    if schedule is None or schedule.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日程不存在")
    schedule_service.delete_schedule(db, schedule)
