"""模型公共基类与混入。

权限预留说明（本轮不实现 RBAC）：
- owner_id：对象归属人（未来权限判断的主体）
- visibility：对象可见范围（PRIVATE / DEPARTMENT / PROJECT / COMPANY）
- member 关系（对象级成员表）将在后续版本以独立的关联表引入，
  本轮仅保留字段与枚举，避免过早设计。
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Visibility(str, enum.Enum):
    """对象可见范围（未来支持 Private / Department / Project / Company）。"""

    PRIVATE = "PRIVATE"
    DEPARTMENT = "DEPARTMENT"
    PROJECT = "PROJECT"
    COMPANY = "COMPANY"


class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=gen_uuid, index=True
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class OwnershipMixin:
    """核心对象的权限预留字段：owner + visibility。"""

    owner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    visibility: Mapped[Visibility] = mapped_column(
        String(20), default=Visibility.COMPANY, nullable=False
    )


class BaseModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __abstract__ = True
