"""AI 工作台相关 Schema：真人状态、AI 分身、代理权限、AI 代处理事项、工作台聚合。"""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.ai_activity import AIActivityType
from app.schemas.chat import ChatRequest
from app.models.employee import (
    DELEGATION_PERMISSION_KEYS,
    DEFAULT_DELEGATION_PERMISSIONS,
    AITwinStatus,
    EmployeeStatus,
)


class WorkbenchChatRequest(ChatRequest):
    """工作台对话请求：可复用已有会话（最近对话）；可携带 Room 上下文。"""

    conversation_id: str | None = None
    room_id: str | None = None


class HumanStatusUpdate(BaseModel):
    """更新真人状态。"""

    status: EmployeeStatus


class AITwinUpdate(BaseModel):
    """更新 AI 分身：名称 / 状态 / 代理权限（均可选）。"""

    ai_twin_name: str | None = Field(default=None, max_length=50)
    ai_twin_status: AITwinStatus | None = None
    ai_permissions: dict[str, bool] | None = None


class WorkbenchProfile(BaseModel):
    user_id: str
    user_name: str
    user_email: str
    employee_id: str | None = None
    company_id: str
    company_name: str
    department_name: str | None = None
    position: str | None = None

    # 真人状态
    human_status: EmployeeStatus = EmployeeStatus.ONLINE
    # AI 分身
    ai_twin_name: str | None = None
    ai_twin_status: AITwinStatus = AITwinStatus.ASSIST
    ai_permissions: dict[str, bool] = Field(
        default_factory=lambda: dict(DEFAULT_DELEGATION_PERMISSIONS)
    )
    ai_twin_display_name: str | None = None

    @property
    def permission_keys(self) -> tuple[str, ...]:
        return DELEGATION_PERMISSION_KEYS


class AIActivityOut(BaseModel):
    id: str
    company_id: str
    employee_id: str
    type: AIActivityType
    title: str
    content: str | None = None
    counterparty: str | None = None
    room_id: str | None = None
    room_name: str | None = None
    task_id: str | None = None
    resolved: bool = False
    created_at: datetime


class AIActivityResolve(BaseModel):
    """处理「待本人确认事项」。"""

    resolved: bool = True
    note: str | None = Field(default=None, max_length=2000)


class ScheduleBrief(BaseModel):
    """工作台里的今日日程卡片。"""

    id: str
    title: str
    start_time: datetime
    end_time: datetime | None = None
    room_id: str | None = None
    room_name: str | None = None
    note: str | None = None


class ProjectUpdateCard(BaseModel):
    """我参与项目的最新 Update。"""

    room_id: str
    room_name: str
    stage: str | None = None
    stage_label: str | None = None
    status: str | None = None
    latest_event_id: str | None = None
    latest_event_type: str | None = None
    latest_event_content: str | None = None
    latest_event_author: str | None = None
    latest_event_at: datetime | None = None
    open_task_count: int = 0


class TaskSummary(BaseModel):
    todo: int = 0
    in_progress: int = 0
    done: int = 0
    overdue: int = 0


class WorkbenchOut(BaseModel):
    profile: WorkbenchProfile
    ai_items: list[AIActivityOut] = Field(default_factory=list)
    today_schedules: list[ScheduleBrief] = Field(default_factory=list)
    project_updates: list[ProjectUpdateCard] = Field(default_factory=list)
    task_summary: TaskSummary = Field(default_factory=TaskSummary)
    today: date
