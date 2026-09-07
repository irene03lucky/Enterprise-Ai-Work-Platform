"""用户模型。

用户是平台级身份，不属于任何单一组织；
其与企业的关联通过 Employee 表表达
（未来还会关联 Room、Knowledge 等对象）。
"""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 反向关系
    employees: Mapped[list["Employee"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    user_roles: Mapped[list["UserRole"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
