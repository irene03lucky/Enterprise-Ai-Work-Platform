from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.employee import (
    DEFAULT_DELEGATION_PERMISSIONS,
    AITwinStatus,
    EmployeeStatus,
)


class EmployeeCreate(BaseModel):
    user_id: str
    department_id: str | None = None
    position: str | None = Field(default=None, max_length=100)
    status: EmployeeStatus = EmployeeStatus.ONLINE


class EmployeeUpdate(BaseModel):
    department_id: str | None = None
    position: str | None = Field(default=None, max_length=100)
    status: EmployeeStatus | None = None


class EmployeeOut(BaseModel):
    id: str
    user_id: str
    company_id: str
    department_id: str | None = None
    position: str | None = None
    status: EmployeeStatus
    ai_twin_name: str | None = None
    ai_twin_status: AITwinStatus = AITwinStatus.ASSIST
    ai_permissions: dict[str, bool] = Field(default_factory=lambda: dict(DEFAULT_DELEGATION_PERMISSIONS))
    ai_twin_display_name: str | None = None
    created_at: datetime
    updated_at: datetime

    # 冗余的用户展示信息，便于前端渲染组织树
    user_name: str | None = None
    user_email: str | None = None
    user_avatar: str | None = None

    model_config = {"from_attributes": True}

    # ---------- 存量数据容错 ----------
    # 历史行可能因「列后加 / 非 ORM 写入」导致 ai_permissions 为 NULL、状态为空，
    # 直接序列化会触发 ResponseValidationError 使整个列表接口 500，这里统一兜底。
    @field_validator("ai_permissions", mode="before")
    @classmethod
    def _normalize_permissions(cls, value: object) -> dict[str, bool]:
        merged = dict(DEFAULT_DELEGATION_PERMISSIONS)
        if isinstance(value, dict):
            merged.update({k: bool(v) for k, v in value.items()})
        return merged

    @field_validator("ai_twin_status", mode="before")
    @classmethod
    def _normalize_twin_status(cls, value: object) -> object:
        return value if value else AITwinStatus.ASSIST

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> object:
        return value if value else EmployeeStatus.ONLINE


class EmployeeUserCreate(BaseModel):
    """一步创建：注册用户并加入企业（管理员建员工场景）。"""

    name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=255)
    password: str = Field(min_length=6, max_length=128)
    department_id: str | None = None
    position: str | None = Field(default=None, max_length=100)
    status: EmployeeStatus = EmployeeStatus.ONLINE
