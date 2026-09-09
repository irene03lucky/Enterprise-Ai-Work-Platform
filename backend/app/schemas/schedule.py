from datetime import datetime

from pydantic import BaseModel, Field

from app.models.schedule import ScheduleVisibility


class ScheduleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    start_time: datetime
    end_time: datetime | None = None
    room_id: str | None = None
    note: str | None = Field(default=None, max_length=4000)
    visibility: ScheduleVisibility = ScheduleVisibility.PRIVATE


class ScheduleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    start_time: datetime | None = None
    end_time: datetime | None = None
    room_id: str | None = None
    note: str | None = Field(default=None, max_length=4000)
    visibility: ScheduleVisibility | None = None


class ScheduleOut(BaseModel):
    id: str
    company_id: str
    user_id: str
    title: str
    start_time: datetime
    end_time: datetime | None = None
    room_id: str | None = None
    room_name: str | None = None
    note: str | None = None
    visibility: ScheduleVisibility
    created_at: datetime
    updated_at: datetime
