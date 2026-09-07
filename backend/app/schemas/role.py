from datetime import datetime

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class RoleAssign(BaseModel):
    user_id: str
    role_id: str


class RoleOut(BaseModel):
    id: str
    company_id: str
    name: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserRoleOut(BaseModel):
    id: str
    user_id: str
    role_id: str

    model_config = {"from_attributes": True}
