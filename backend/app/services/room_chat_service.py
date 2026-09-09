"""Room 项目聊天服务层：消息沉淀 + AI 分身接管 + 任务/项目 Update 闭环。

接管条件（全部满足才接管；缺一则 AI 旁观）：
1. 目标成员 AI 分身状态 = AGENT（开启代理）；
2. 目标成员真人状态不适合即时处理（会议中/客户拜访/出差/请假/离线）；
3. 消息在其授权范围内（answer_project_info）；
4. 消息点名（包含成员姓名）了该成员。

接管后：
- 生成「XX「状态」 XX·AI分身 已接管当前聊天」的系统提示（项目群公开）；
- 基于 Room 上下文（阶段 / Work Event / 任务 / 最近聊天）生成回复；
- 若识别出后续行动且拥有 create_task 权限 → 创建成员个人 Task（进入 Work Center）
  + 同步一条「新增任务」项目 Update 到 Timeline。
"""

from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.llm import get_chat_model
from app.models import (
    AIActivityType,
    EventVisibility,
    Room,
    RoomChatMessage,
    RoomMember,
    TaskSource,
    TaskStatus,
    WorkEvent,
    WorkEventType,
)
from app.schemas.task import TaskCreate
from app.services import project_agent_service, task_service, workbench_service

STAGE_LABELS = {
    "CONTACT": "接触",
    "NEGOTIATION": "洽谈",
    "CONTRACT_DRAFT": "合同打磨",
    "SIGNED": "签约",
    "DELIVERY": "交付",
    "ACCEPTANCE": "验收",
}

HUMAN_STATUS_LABELS = {
    "ONLINE": "在线",
    "IN_MEETING": "会议中",
    "CUSTOMER_VISIT": "客户拜访",
    "BUSINESS_TRIP": "出差",
    "LEAVE": "请假",
    "OFFLINE": "离线",
    "ACTIVE": "在线",  # 历史取值兼容
}

# 真人状态不适合即时处理的状态集合（此时 AI 分身才可能接管）
BUSY_STATUSES = {"IN_MEETING", "CUSTOMER_VISIT", "BUSINESS_TRIP", "LEAVE", "OFFLINE"}


def _enum_value(v) -> str:
    return str(getattr(v, "value", v))


def list_messages(db: Session, room_id: str, limit: int = 100) -> list[RoomChatMessage]:
    """按时间正序返回最近 limit 条消息。"""
    rows = list(
        db.scalars(
            select(RoomChatMessage)
            .where(RoomChatMessage.room_id == room_id)
            .options(
                selectinload(RoomChatMessage.employee).selectinload(RoomChatMessage.employee.user)
            )
            .order_by(RoomChatMessage.created_at.asc(), RoomChatMessage.id.asc())
        ).all()
    )
    return rows[-limit:]


def _is_busy(emp) -> bool:
    return _enum_value(emp.status) in BUSY_STATUSES


def _status_label(emp) -> str:
    return HUMAN_STATUS_LABELS.get(_enum_value(emp.status), "在线")


def _twin_status(emp) -> str:
    return _enum_value(emp.ai_twin_status)


def _sender_name(m: RoomChatMessage) -> str | None:
    if m.sender_kind == "AI":
        return m.employee.ai_twin_display_name if m.employee else None
    if m.sender_kind == "USER":
        return m.employee.user.name if m.employee and m.employee.user else None
    return None


async def _generate_reply(db: Session, room: Room, emp, question: str) -> str:
    """基于 Room 项目上下文生成分身回复。失败时退化为兜底话术。"""
    stage = _enum_value(room.stage)
    lines = [f"项目：{room.name}（当前阶段：{STAGE_LABELS.get(stage, stage)}）"]
    if room.description:
        lines.append(f"项目简介：{room.description[:200]}")
    events = list(
        db.scalars(
            select(WorkEvent)
            .where(WorkEvent.room_id == room.id)
            .order_by(WorkEvent.event_date.desc())
            .limit(5)
        ).all()
    )
    if events:
        lines.append("最近动态：" + "；".join(e.content[:80] for e in reversed(events)))
    open_tasks = [t for t in task_service.list_room_tasks(db, room.id) if t.status != TaskStatus.DONE][:5]
    if open_tasks:
        lines.append("进行中任务：" + "；".join(t.title for t in open_tasks))
    recent = list_messages(db, room.id, limit=6)
    if recent:
        lines.append(
            "最近聊天："
            + "；".join(f"{_sender_name(m) or '系统'}：{m.content[:60]}" for m in recent)
        )
    context = "\n".join(lines)

    system = (
        f"你是{emp.ai_twin_display_name}，在项目群中代表{emp.user.name}回复。"
        "基于项目上下文简洁回答，不超过3句话；不确定的信息要说明会向本人确认后回复，不要编造。"
    )
    try:
        result = await get_chat_model().ainvoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=f"项目上下文：\n{context}\n\n群消息：{question}"),
            ]
        )
        text = str(result.content).strip()
        return (text or "已收到消息，稍后向本人确认后回复。")[:1000]
    except Exception:  # noqa: BLE001
        return (
            f"收到，{emp.user.name}当前「{_status_label(emp)}」中，"
            "我会尽快跟进这条消息并同步进展。"
        )


async def send_message(
    db: Session, room: Room, sender_employee, content: str
) -> list[RoomChatMessage]:
    """发送一条项目聊天消息，并按授权情况触发 AI 分身接管。"""
    now = datetime.now(timezone.utc)
    user_msg = RoomChatMessage(
        room_id=room.id,
        employee_id=sender_employee.id if sender_employee else None,
        sender_kind="USER",
        content=content,
        created_at=now,
        updated_at=now,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)
    created: list[RoomChatMessage] = [user_msg]

    # 找出被点名的其他成员（消息内容包含其姓名）
    members = list(
        db.scalars(
            select(RoomMember)
            .where(RoomMember.room_id == room.id)
            .options(selectinload(RoomMember.employee).selectinload(RoomMember.employee.user))
        ).all()
    )
    for m in members:
        emp = m.employee
        if emp is None or emp.user is None:
            continue
        if sender_employee is not None and emp.id == sender_employee.id:
            continue
        name = emp.user.name
        if not name or name not in content:
            continue

        busy = _is_busy(emp)
        agent_on = _twin_status(emp) == AITwinStatus.AGENT.value
        permissions = emp.effective_permissions()

        if busy and agent_on and permissions.get("answer_project_info"):
            # 1) 系统提示：AI 已接管（项目群公开可见）
            sys_now = datetime.now(timezone.utc)
            takeover = RoomChatMessage(
                room_id=room.id,
                employee_id=None,
                sender_kind="SYSTEM",
                content=f"{name}「{_status_label(emp)}」 {emp.ai_twin_display_name} 已接管当前聊天",
                created_at=sys_now,
                updated_at=sys_now,
            )
            db.add(takeover)
            db.commit()
            db.refresh(takeover)
            created.append(takeover)

            # 2) 生成分身回复
            reply_text = await _generate_reply(db, room, emp, content)
            reply_now = datetime.now(timezone.utc)
            reply = RoomChatMessage(
                room_id=room.id,
                employee_id=emp.id,
                sender_kind="AI",
                content=reply_text,
                created_at=reply_now,
                updated_at=reply_now,
            )
            db.add(reply)
            db.commit()
            db.refresh(reply)
            created.append(reply)

            # 3) 识别后续行动 → 生成个人 Task + 项目 Update
            if permissions.get("create_task"):
                try:
                    _, proposals = await project_agent_service.detect_and_extract(
                        content, {"member_names": []}
                    )
                except Exception:  # noqa: BLE001
                    proposals = []
                for proposal in proposals[:1]:
                    task = task_service.create_company_task(
                        db,
                        company_id=room.company_id,
                        data=TaskCreate(
                            title=proposal.title[:200],
                            description=proposal.description,
                            room_id=room.id,
                            assignee_employee_id=emp.id,
                        ),
                        created_by=emp.user_id,
                        source=TaskSource.AI_TWIN,
                        source_quote=content,
                    )
                    workbench_service.record_activity(
                        db,
                        room.company_id,
                        emp.id,
                        AIActivityType.TASK_CREATED,
                        title=f"AI 分身生成任务：{task.title}",
                        content=f"来源消息：{content}",
                        counterparty=f"项目聊天 · {room.name}",
                        room_id=room.id,
                        task_id=task.id,
                    )
                    db.add(
                        WorkEvent(
                            room_id=room.id,
                            employee_id=emp.id,
                            type=WorkEventType.TASK_UPDATE,
                            visibility=EventVisibility.PUBLIC,
                            content=(
                                f"{name} 新增任务：{task.title}"
                                f"（来源：项目聊天）｜状态：处理中"
                            ),
                        )
                    )
                    db.commit()
                    break
        elif busy and agent_on:
            # 开启了代理但超出授权范围 → 转待本人确认
            denied_now = datetime.now(timezone.utc)
            denied = RoomChatMessage(
                room_id=room.id,
                employee_id=None,
                sender_kind="SYSTEM",
                content=(
                    f"{name}「{_status_label(emp)}」 {emp.ai_twin_display_name} "
                    f"超出代理权限，待本人处理"
                ),
                created_at=denied_now,
                updated_at=denied_now,
            )
            db.add(denied)
            db.commit()
            db.refresh(denied)
            created.append(denied)
            workbench_service.record_activity(
                db,
                room.company_id,
                emp.id,
                AIActivityType.NEED_CONFIRM,
                title=f"项目聊天超出代理权限：{content[:40]}",
                content=f"来自「{room.name}」项目聊天：{content}",
                counterparty=name,
                room_id=room.id,
            )

    return created
