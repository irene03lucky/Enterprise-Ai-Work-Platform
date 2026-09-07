"""知识空间与文档资产模型。

知识库定位为企业数据资产：KnowledgeSpace 是企业内的知识分区，
KnowledgeDocument 是受管理的文档资产（含解析与向量化状态），
而非简单文件存储。
"""

from enum import Enum as PyEnum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, OwnershipMixin


class DocumentStatus(str, PyEnum):
    """文档资产的处理状态机：UPLOADED → PARSING → EMBEDDING → READY / FAILED。"""

    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    EMBEDDING = "EMBEDDING"
    READY = "READY"
    FAILED = "FAILED"


class KnowledgeSpace(BaseModel, OwnershipMixin):
    """知识空间：企业知识的分区容器。

    visibility 继承自 OwnershipMixin（COMPANY / DEPARTMENT / PRIVATE），
    本轮统一按企业可见处理，字段为未来权限模型预留。
    """

    __tablename__ = "knowledge_spaces"

    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )


class KnowledgeDocument(BaseModel):
    """文档资产：受管理的知识载体（含向量化状态、分块数、溯源信息）。"""

    __tablename__ = "knowledge_documents"

    knowledge_space_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_spaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.UPLOADED, nullable=False, index=True
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploader_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    space = relationship("KnowledgeSpace", back_populates="documents")
