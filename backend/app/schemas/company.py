from datetime import datetime

from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    industry: str | None = Field(default=None, max_length=100)
    logo: str | None = Field(default=None, max_length=500)


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    industry: str | None = Field(default=None, max_length=100)
    logo: str | None = Field(default=None, max_length=500)


class CompanyBrief(BaseModel):
    id: str
    name: str
    industry: str | None = None
    logo: str | None = None

    model_config = {"from_attributes": True}


class CompanyOut(CompanyBrief):
    description: str | None = None
    owner_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
