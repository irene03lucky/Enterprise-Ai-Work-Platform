from datetime import datetime

from pydantic import BaseModel, Field

from app.models.base import Visibility
from app.models.knowledge import DocumentStatus


class KnowledgeSpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    visibility: Visibility = Visibility.COMPANY


class KnowledgeSpaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class KnowledgeSpaceOut(BaseModel):
    id: str
    company_id: str
    name: str
    description: str | None = None
    visibility: Visibility
    owner_id: str | None = None
    document_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeDocumentOut(BaseModel):
    id: str
    knowledge_space_id: str
    company_id: str
    name: str
    file_type: str
    file_size: int
    status: DocumentStatus | str
    chunk_count: int
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
