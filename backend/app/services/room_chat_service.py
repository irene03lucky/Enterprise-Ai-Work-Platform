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

import re
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.llm import get_chat_model
from app.models import (
    AIActivityType,
    AITwinStatus,
    Employee,
    EventVisibility,
    Room,
    RoomChatMessage,
    RoomMember,
    TaskSource,
    TaskStatus,
    User,
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

TASK_STATUS_LABELS = {"TODO": "待办", "IN_PROGRESS": "进行中", "DONE": "已完成"}

# 群内点名：容忍「@张三」「@ 张三」「@张三 你好」等写法
_MENTION_RE = re.compile(r"@\s*([^\s@，,。.；;：:！!？?、\"'（）()\[\]]{1,20})")
# 这些不是具体成员，命中时不做「未找到成员」提示
_MENTION_IGNORE = {"所有人", "全体", "全员", "all", "here", "团队"}


def _enum_value(v) -> str:
    return str(getattr(v, "value", v))


def extract_mentions(content: str) -> list[str]:
    """提取消息里被 @ 的成员名（去重、保序）。"""
    found: list[str] = []
    for raw in _MENTION_RE.findall(content or ""):
        name = raw.strip()
        if name and name not in found and name not in _MENTION_IGNORE:
            found.append(name)
    return found


def _system_note(db: Session, room: Room, content: str) -> RoomChatMessage:
    """写入一条系统提示（项目群公开可见），用于说明「为什么没有人接管」。"""
    now = datetime.now(timezone.utc)
    note = RoomChatMessage(
        room_id=room.id,
        employee_id=None,
        sender_kind="SYSTEM",
        content=content,
        created_at=now,
        updated_at=now,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_messages(db: Session, room_id: str, limit: int = 100) -> list[RoomChatMessage]:
    """按时间正序返回最近 limit 条消息。"""
    rows = list(
        db.scalars(
            select(RoomChatMessage)
            .where(RoomChatMessage.room_id == room_id)
            .options(selectinload(RoomChatMessage.employee).selectinload(Employee.user))
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


async def _generate_reply(db: Session, room: Room, emp, question: str, asker=None) -> str:
    """基于 Room 项目上下文生成分身回复。失败时退化为兜底话术。"""
    stage = _enum_value(room.stage)
    lines = [f"项目：{room.name}（当前阶段：{STAGE_LABELS.get(stage, stage)}）"]
    if room.description:
        lines.append(f"项目简介：{room.description[:200]}")

    # 项目成员（含真人状态与分身状态）：分身必须知道「群里都有谁、谁在忙」，
    # 否则会把同事当成外人、或对群里根本不存在的人作答。
    members = list(
        db.scalars(
            select(RoomMember)
            .where(RoomMember.room_id == room.id)
            .options(selectinload(RoomMember.employee).selectinload(Employee.user))
        ).all()
    )
    member_desc: list[str] = []
    for m in members:
        e = m.employee
        if e is None or e.user is None:
            continue
        twin = (
            "已开启代理"
            if _twin_status(e) == AITwinStatus.AGENT.value
            else ("仅辅助" if _twin_status(e) == AITwinStatus.ASSIST.value else "已关闭")
        )
        member_desc.append(
            f"{e.user.name}（{'负责人' if m.role == 'OWNER' else '成员'}"
            f"·{_status_label(e)}·AI分身{twin}）"
        )
    if member_desc:
        lines.append("项目成员：" + "；".join(member_desc))

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
    # 任务必须带负责人与状态：只给标题时模型会臆断归属
    # （曾把「整理数字人导览需求清单并给出报价」说成别人在准备）。
    room_tasks = task_service.list_room_tasks(db, room.id)
    if room_tasks:
        lines.append("项目任务（含负责人与状态）：")
        for t in room_tasks[:8]:
            assignee_name = (
                t.assignee.user.name
                if getattr(t, "assignee", None) and t.assignee.user
                else "未分配"
            )
            lines.append(
                f"- {t.title}｜负责人：{assignee_name}"
                f"｜状态：{TASK_STATUS_LABELS.get(_enum_value(t.status), _enum_value(t.status))}"
            )
    recent = list_messages(db, room.id, limit=6)
    if recent:
        lines.append(
            "最近聊天："
            + "；".join(f"{_sender_name(m) or '系统'}：{m.content[:60]}" for m in recent)
        )
    if asker is not None and asker.user is not None:
        lines.append(
            f"本次提问者：{asker.user.name}（{asker.position or '项目成员'}"
            f"·{_status_label(asker)}）—— 他是项目里的同事，不是 {emp.user.name} 本人。"
        )
    context = "\n".join(lines)

    system = (
        f"你是{emp.ai_twin_display_name}，在项目群中代表{emp.user.name}回复同事。"
        "只依据下面给出的项目上下文回答，简洁、不超过3句话。\n"
        "禁止编造：不要说「我正在准备/正在处理/马上给您」这类你无法确认的进度承诺；"
        "任务或事项的负责人、状态必须与上下文一致（例如「这条由张三负责，状态待办」），"
        "上下文里没有的信息就直说你还无法确认。\n"
        f"只有确实需要{emp.user.name}本人拍板的事（时间、金额、报价、对外正式回复），"
        f"才回答「这需要{emp.user.name}本人确认」；其余问题直接作答。"
    )
    try:
        result = await get_chat_model().ainvoke(
            [
                SystemMessage(content=system),
                HumanMessage(
            content=(
                f"项目上下文：\n{context}\n\n群消息：{question}\n\n"
                "（只回复这一条群消息；不要续写对话、不要模拟其他人发言、"
                "不要输出说话人名字或签名。）"
            )
        ),
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
    mentions = extract_mentions(content)

    # 找出被点名的其他成员（消息内容包含其姓名）
    members = list(
        db.scalars(
            select(RoomMember)
            .where(RoomMember.room_id == room.id)
            .options(selectinload(RoomMember.employee).selectinload(Employee.user))
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
            created.append(
                _system_note(
                    db,
                    room,
                    f"{name}「{_status_label(emp)}」 {emp.ai_twin_display_name} 已接管当前聊天",
                )
            )

            # 2) 生成分身回复
            reply_text = await _generate_reply(db, room, emp, content, asker=sender_employee)
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
                for proposal in proposals[:3]:
                    title = (proposal.title or "").strip()
                    # 疑问句 / 点名文本不是可执行任务：模型曾把
                    # 「@平台管理员 数字人导览的报价什么时候能给我」整句当成任务标题，
                    # 污染项目任务列表，这里直接丢弃这类提案。
                    if (
                        not title
                        or "@" in title
                        or title.endswith(("？", "?", "！", "!", "。"))
                    ):
                        continue
                    task = task_service.create_company_task(
                        db,
                        company_id=room.company_id,
                        data=TaskCreate(
                            title=title[:200],
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
            created.append(
                _system_note(
                    db,
                    room,
                    f"{name}「{_status_label(emp)}」 {emp.ai_twin_display_name} "
                    "超出代理权限，待本人处理",
                )
            )
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
        elif name in mentions:
            # 点名了成员但不会有人接管（分身未开代理 / 本人可即时处理）：
            # 明确说明原因。此前是静默无响应，用户会以为系统「不认识这个人」。
            reason = (
                "其 AI 分身未开启代理，本条待本人回复"
                if not agent_on
                else "其当前可即时处理，本条待本人回复"
            )
            created.append(
                _system_note(db, room, f"{name}「{_status_label(emp)}」：{reason}")
            )

    # 点名了项目外的人 / 名字拼错 → 同样给出明确说明，不留「发了没反应」
    member_names = {
        m.employee.user.name
        for m in members
        if m.employee is not None and m.employee.user is not None
    }
    sender_name = sender_employee.user.name if sender_employee is not None and sender_employee.user else None
    for token in mentions:
        if token in member_names or token == sender_name:
            continue
        employee_row = db.scalar(
            select(Employee)
            .join(Employee.user)
            .where(Employee.company_id == room.company_id, User.name == token)
        )
        if employee_row is not None:
            note = (
                f"「{token}」还不是本项目成员，不会被点名响应；"
                "可由项目成员在左侧「+ 添加」把他加入项目"
            )
        else:
            note = f"未在项目成员中找到「{token}」，可点击聊天上方的成员标签自动补全"
        created.append(_system_note(db, room, note))

    return created


def clear_messages(db: Session, room_id: str) -> int:
    """清空某个项目的聊天记录（「清屏」），返回删除条数。"""
    rows = list(
        db.scalars(select(RoomChatMessage).where(RoomChatMessage.room_id == room_id)).all()
    )
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)
