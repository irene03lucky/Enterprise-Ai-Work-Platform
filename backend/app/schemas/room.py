from datetime import datetime

from pydantic import BaseModel, Field

from app.models.room import EventVisibility, RoomStage, RoomStatus, WorkEventType


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: RoomStatus = RoomStatus.ACTIVE
    stage: RoomStage = RoomStage.CONTACT


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: RoomStatus | None = None
    stage: RoomStage | None = None


class RoomMemberAdd(BaseModel):
    employee_id: str


class RoomDocumentAdd(BaseModel):
    document_id: str


class WorkEventCreate(BaseModel):
    type: WorkEventType
    content: str = Field(min_length=1, max_length=8000)
    event_date: datetime | None = None
    # PUBLIC=公开里程碑（相关部门可见）；INTERNAL=内部事件（仅项目成员/管理层）
    visibility: EventVisibility = EventVisibility.INTERNAL


class RoomOut(BaseModel):
    id: str
    company_id: str
    name: str
    description: str | None = None
    status: RoomStatus
    stage: RoomStage = RoomStage.CONTACT
    stage_label: str | None = None
    stage_updated_at: datetime | None = None
    # 当前访问者可见深度：member（项目成员/管理层）| related（相关部门等其他成员）
    access_level: str = "related"
    owner_id: str | None = None
    member_count: int = 0
    event_count: int = 0
    open_task_count: int = 0
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
    # 项目群公开协作信息：真人状态 + AI 分身接管状态
    human_status: str | None = None
    ai_twin_status: str | None = None
    ai_twin_display_name: str | None = None
    created_at: datetime


class RoomChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class RoomChatMessageOut(BaseModel):
    id: str
    room_id: str
    employee_id: str | None = None
    # USER=成员本人 / AI=成员的 AI 分身 / SYSTEM=系统提示（AI 接管状态等）
    sender_kind: str
    sender_name: str | None = None
    content: str
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
    visibility: EventVisibility = EventVisibility.INTERNAL
    event_date: datetime
    author_name: str | None = None
    author_position: str | None = None
    created_at: datetime
