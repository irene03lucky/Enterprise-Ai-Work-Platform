from datetime import datetime

from pydantic import BaseModel, Field

from app.models.room import RoomStatus, WorkEventType


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: RoomStatus = RoomStatus.ACTIVE


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: RoomStatus | None = None


class RoomMemberAdd(BaseModel):
    employee_id: str


class RoomDocumentAdd(BaseModel):
    document_id: str


class WorkEventCreate(BaseModel):
    type: WorkEventType
    content: str = Field(min_length=1, max_length=8000)
    event_date: datetime | None = None


class RoomOut(BaseModel):
    id: str
    company_id: str
    name: str
    description: str | None = None
    status: RoomStatus
    owner_id: str | None = None
    member_count: int = 0
    event_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class RoomMemberOut(BaseModel):
    id: str
    room_id: str
    employee_id: str
    role: str
    user_name: str | None = None
    user_email: str | None = None
    position: str | None = None
    department_name: str | None = None
    created_at: datetime


class RoomDocumentOut(BaseModel):
    id: str
    room_id: str
    document_id: str
    document_name: str | None = None
    document_status: str | None = None
    chunk_count: int | None = None
    created_at: datetime


class WorkEventOut(BaseModel):
    id: str
    room_id: str
    employee_id: str | None = None
    type: WorkEventType
    content: str
    event_date: datetime
    author_name: str | None = None
    author_position: str | None = None
    created_at: datetime
