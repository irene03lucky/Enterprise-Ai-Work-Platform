from pydantic import BaseModel, EmailStr, Field

from app.models.employee import EmployeeStatus


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    avatar: str | None = None

    model_config = {"from_attributes": True}


class CompanyMembership(BaseModel):
    """用户在某个企业空间中的身份：公司信息 + 员工档案摘要（含部门）。"""

    id: str
    name: str
    industry: str | None = None
    logo: str | None = None
    employee_id: str | None = None
    department_id: str | None = None
    department_name: str | None = None
    position: str | None = None
    status: EmployeeStatus | None = None


class MeResponse(BaseModel):
    user: UserOut
    companies: list[CompanyMembership] = []
