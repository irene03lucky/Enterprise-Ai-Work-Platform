"""日程服务层：创建与查询轻量日程（私人/公司分类暂不展开，仅预留 visibility）。"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate


def list_schedules(
    db: Session,
    company_id: str,
    user_id: str,
    day: date | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Schedule]:
    stmt = (
        select(Schedule)
        .where(Schedule.company_id == company_id, Schedule.user_id == user_id)
        .options(selectinload(Schedule.room))
    )
    if start is not None:
        stmt = stmt.where(Schedule.start_time >= start)
    if end is not None:
        stmt = stmt.where(Schedule.start_time <= end)
    schedules = list(db.scalars(stmt.order_by(Schedule.start_time)).all())

    if day is not None and start is None and end is None:
        schedules = [s for s in schedules if _local_day(s.start_time) == day]
    return schedules


def _local_day(value: datetime) -> date:
    return value.astimezone().date() if value.tzinfo else value.date()


def get_schedule(db: Session, schedule_id: str, user_id: str) -> Schedule | None:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None or schedule.user_id != user_id:
        return None
    return schedule


def create_schedule(
    db: Session, company_id: str, user_id: str, data: ScheduleCreate
) -> Schedule:
    schedule = Schedule(
        company_id=company_id,
        user_id=user_id,
        title=data.title,
        start_time=data.start_time,
        end_time=data.end_time,
        room_id=data.room_id,
        note=data.note,
        visibility=data.visibility,
        owner_id=user_id,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def update_schedule(db: Session, schedule: Schedule, data: ScheduleUpdate) -> Schedule:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)
    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule: Schedule) -> None:
    db.delete(schedule)
    db.commit()
