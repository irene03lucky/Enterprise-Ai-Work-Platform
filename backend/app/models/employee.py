"""员工模型：用户在企业空间中的身份 + 真人状态 + AI 数字分身。

两类状态相互独立，产品语义不同：
- 真人状态（status）：员工本人当前的工作状态（在线/会议中/客户拜访/出差/请假/离线），
  是 AI 判断"能不能找到本人"的信号，不是考勤。
- AI 分身状态（ai_twin_status）：AI 代本人工作的程度（关闭/仅辅助/开启代理），
  决定 AI 能否在授权范围内代替本人回应与接收工作事项。

代理权限（ai_permissions）以勾选框形式暴露，AI 只能在已授权范围内代理，
未授权项（如代发正式业务回复、承诺时间/金额）必须交回本人处理。
"""

import enum

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class EmployeeStatus(str, enum.Enum):
    """真人状态。"""

    ONLINE = "ONLINE"  # 在线
    IN_MEETING = "IN_MEETING"  # 会议中
    CUSTOMER_VISIT = "CUSTOMER_VISIT"  # 客户拜访
    BUSINESS_TRIP = "BUSINESS_TRIP"  # 出差
    LEAVE = "LEAVE"  # 请假
    OFFLINE = "OFFLINE"  # 离线
    ACTIVE = "ACTIVE"  # 历史取值，等价于 ONLINE（兼容存量数据）


class AITwinStatus(str, enum.Enum):
    """AI 数字分身状态：关闭 / 仅辅助 / 开启代理。"""

    OFF = "OFF"
    ASSIST = "ASSIST"
    AGENT = "AGENT"


# AI 分身可代理的权限项（键 → 展示文案在前端维护）
DELEGATION_PERMISSION_KEYS = (
    "answer_project_info",  # 回答项目授权信息
    "report_status",  # 汇报真人当前状态
    "receive_work_items",  # 接收工作事项
    "create_task",  # 创建 Task
    "provide_project_docs",  # 提供已有项目资料
    "send_formal_reply",  # 代发正式业务回复
    "commit_time_or_money",  # 承诺时间/金额
)

DEFAULT_DELEGATION_PERMISSIONS: dict[str, bool] = {
    "answer_project_info": True,
    "report_status": True,
    "receive_work_items": True,
    "create_task": True,
    "provide_project_docs": True,
    "send_formal_reply": False,
    "commit_time_or_money": False,
}


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

    # ---------- 真人状态 ----------
    status: Mapped[EmployeeStatus] = mapped_column(
        String(20), default=EmployeeStatus.ONLINE, nullable=False
    )

    # ---------- AI 数字分身 ----------
    # 自定义分身名称（本人视角使用）
    ai_twin_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_twin_status: Mapped[AITwinStatus] = mapped_column(
        String(20), default=AITwinStatus.ASSIST, nullable=False
    )
    # 代理权限开关：{key: bool}
    ai_permissions: Mapped[dict] = mapped_column(
        JSON, default=lambda: dict(DEFAULT_DELEGATION_PERMISSIONS), nullable=False
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

    @property
    def ai_twin_display_name(self) -> str:
        """对同事统一展示的 AI 分身名称：「本人姓名 · AI分身」."""
        base = self.user.name if self.user else "同事"
        return f"{base} · AI分身"

    def effective_permissions(self) -> dict[str, bool]:
        """合并默认值的有效权限（容忍历史数据中缺失的键）。"""
        merged = dict(DEFAULT_DELEGATION_PERMISSIONS)
        merged.update(self.ai_permissions or {})
        return merged
