"""企业模型：代表一个企业空间。

未来所有 Knowledge / Room / Employee / Agent 等对象
均挂载在 Company 之下。
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, OwnershipMixin


class Company(BaseModel, OwnershipMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 组织结构
    departments: Mapped[list["Department"]] = relationship(  # noqa: F821
        back_populates="company",
        foreign_keys="Department.company_id",
        cascade="all, delete-orphan",
    )
    employees: Mapped[list["Employee"]] = relationship(  # noqa: F821
        back_populates="company", cascade="all, delete-orphan"
    )
    roles: Mapped[list["Role"]] = relationship(  # noqa: F821
        back_populates="company", cascade="all, delete-orphan"
    )
