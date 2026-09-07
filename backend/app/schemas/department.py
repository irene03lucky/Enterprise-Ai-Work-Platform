from datetime import datetime

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None
    description: str | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: str | None = None
    description: str | None = None


class DepartmentOut(BaseModel):
    id: str
    company_id: str
    parent_id: str | None = None
    name: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
