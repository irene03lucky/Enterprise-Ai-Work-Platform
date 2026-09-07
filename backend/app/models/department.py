"""部门模型：树状组织结构，支持无限层级。"""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Department(BaseModel):
    __tablename__ = "departments"

    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="CASCADE"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    company = relationship("Company", back_populates="departments", foreign_keys=[company_id])
    parent = relationship("Department", remote_side="Department.id", back_populates="children")
    children = relationship(
        "Department", back_populates="parent", cascade="all, delete-orphan"
    )
    employees: Mapped[list["Employee"]] = relationship(  # noqa: F821
        back_populates="department"
    )
