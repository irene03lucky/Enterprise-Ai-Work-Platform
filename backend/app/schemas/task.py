"""Task 请求/响应模型，以及 AI 任务提案（Proposal）结构。

Proposal 是「AI 识别到的行动事项」，不会自动落库：
前端展示为确认卡片，用户确认后才调用创建接口生成 Task。
"""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.task import TaskSource, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    # Task 统一在 AI 工作台管理，可不属于任何项目
    room_id: str | None = None
    assignee_employee_id: str | None = None
    due_date: date | None = None
    status: TaskStatus = TaskStatus.TODO


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    room_id: str | None = None
    assignee_employee_id: str | None = None
    due_date: date | None = None
    status: TaskStatus | None = None


class TaskProposal(BaseModel):
    """AI 识别出的任务提案（待确认）。"""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    assignee_name: str | None = None
    assignee_employee_id: str | None = None
    due_date: date | None = None
    source: TaskSource = TaskSource.CHAT
    source_event_id: str | None = None
    source_quote: str | None = Field(default=None, max_length=4000)


class TaskProposalConfirm(BaseModel):
    proposals: list[TaskProposal] = Field(default_factory=list, max_length=10)


class TaskOut(BaseModel):
    id: str
    company_id: str
    room_id: str | None = None
    room_name: str | None = None
    title: str
    description: str | None = None
    assignee_employee_id: str | None = None
    assignee_name: str | None = None
    due_date: date | None = None
    status: TaskStatus
    source: TaskSource
    source_event_id: str | None = None
    source_quote: str | None = None
    created_by: str | None = None
    creator_name: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
