from datetime import datetime

from pydantic import BaseModel, Field

from app.models.employee import EmployeeStatus


class EmployeeCreate(BaseModel):
    user_id: str
    department_id: str | None = None
    position: str | None = Field(default=None, max_length=100)
    status: EmployeeStatus = EmployeeStatus.ACTIVE


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
    created_at: datetime
    updated_at: datetime

    # 冗余的用户展示信息，便于前端渲染组织树
    user_name: str | None = None
    user_email: str | None = None
    user_avatar: str | None = None

    model_config = {"from_attributes": True}


class EmployeeUserCreate(BaseModel):
    """一步创建：注册用户并加入企业（管理员建员工场景）。"""

    name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=255)
    password: str = Field(min_length=6, max_length=128)
    department_id: str | None = None
    position: str | None = Field(default=None, max_length=100)
    status: EmployeeStatus = EmployeeStatus.ACTIVE
