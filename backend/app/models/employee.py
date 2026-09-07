"""员工模型：用户在企业空间中的身份。

注意：status 不是考勤字段，而是供未来 AI
理解员工当前工作状态的轻量信号。
"""

import enum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    LEAVE = "LEAVE"
    BUSINESS_TRIP = "BUSINESS_TRIP"
    OFFLINE = "OFFLINE"


class Employee(BaseModel):
    __tablename__ = "employees"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    department_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[EmployeeStatus] = mapped_column(
        String(20), default=EmployeeStatus.ACTIVE, nullable=False
    )

    user = relationship("User", back_populates="employees")
    company = relationship("Company", back_populates="employees")
    department = relationship("Department", back_populates="employees")

    # 只读属性，供 Pydantic from_attributes 序列化为冗余展示字段
    @property
    def user_name(self) -> str | None:
        return self.user.name if self.user else None

    @property
    def user_email(self) -> str | None:
        return self.user.email if self.user else None

    @property
    def user_avatar(self) -> str | None:
        return self.user.avatar if self.user else None
