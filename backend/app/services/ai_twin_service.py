"""AI 数字分身代理：在授权范围内代替本人回应、接收工作事项与生成 Task。

代理边界（严格执行）：
- AI 分身状态 OFF：不代理本人，不汇报本人状态，不接收/创建任务；
- ASSIST：可按权限回答问题并接收事项，但不自动创建 Task（只给提案）；
- AGENT：明确工作指令且已授权 create_task 时自动创建 Task；
- 未授权项（代发正式业务回复、承诺时间/金额）一律拒绝并交回本人；
- 模糊但需本人处理的事项 → 记录为「待本人确认」，不擅自行动；
- 普通聊天绝不自动生成任务。

每一次代处理都会写入 AIActivity，在 AI 工作台前置展示。
"""

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.ai.llm import get_chat_model
from app.models import (
    AIActivityType,
    AITwinStatus,
    DEFAULT_DELEGATION_PERMISSIONS,
    Employee,
    EmployeeStatus,
    TaskSource,
)
from app.schemas.task import TaskCreate, TaskProposal
from app.services import (
    conversation_service,
    project_agent_service,
    rag_service,
    task_service,
    workbench_service,
)

logger = logging.getLogger(__name__)

INTENT_QUERY = "QUERY"
INTENT_ACTION = "ACTION"
INTENT_FOLLOW_UP = "FOLLOW_UP"
INTENT_AMBIGUOUS = "AMBIGUOUS"

# 模糊表达：无法确定具体动作/时间，需交回本人确认
VAGUE_MARKERS = (
    "那个事", "那件事", "有空", "帮忙看看", "看一下", "处理一下", "你看着办",
    "再说", "问问他", "找时间", "尽快", "合适的时候", "看着处理", "商量一下",
)
# 需要高权限代理：正式对外回复 / 承诺时间与金额
COMMIT_MARKERS = (
    "承诺", "保证", "报价", "交期", "多久能交付", "回复客户", "发给客户",
    "签订合同", "确认金额", "降价", "折扣",
)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


def classify_twin_intent(question: str) -> str:
    """在工作台场景下的意图识别（比 Project Agent 多一个「模糊」类）。"""
    base = project_agent_service.classify_intent(question)
    if base == project_agent_service.INTENT_ACTION:
        return INTENT_ACTION
    if base == project_agent_service.INTENT_FOLLOW_UP:
        return INTENT_FOLLOW_UP
    text = question.strip()
    if any(m in text for m in VAGUE_MARKERS):
        return INTENT_AMBIGUOUS
    return INTENT_QUERY


def needs_high_risk_permission(question: str) -> bool:
    """是否涉及「代发正式业务回复 / 承诺时间与金额」。"""
    return any(m in question for m in COMMIT_MARKERS)


def _human_status_label(status) -> str:
    value = status.value if hasattr(status, "value") else str(status)
    return {
        "ONLINE": "在线",
        "IN_MEETING": "会议中",
        "CUSTOMER_VISIT": "客户拜访",
        "BUSINESS_TRIP": "出差",
        "LEAVE": "请假",
        "OFFLINE": "离线",
        "ACTIVE": "在线",
    }.get(value, value)


def build_workbench_context_block(
    db: Session, company, user, employee: Employee | None
) -> str:
    """把「我是谁 + 我的日程 + 我的项目 + 我的任务」注入提示词。"""
    lines = ["【本人信息】", f"姓名：{user.name}"]
    if employee is not None:
        lines.append(
            f"部门：{employee.department.name if employee.department else '未分配'}"
            f" · 职位：{employee.position or '未设置'}"
        )
        lines.append(f"真人状态：{_human_status_label(employee.status)}")
        lines.append(
            f"AI 分身：{employee.ai_twin_name or employee.ai_twin_display_name}"
            f"（状态 {employee.ai_twin_status.value if hasattr(employee.ai_twin_status, 'value') else employee.ai_twin_status}）"
        )
    lines.append(f"企业：{company.name}")

    if employee is None:
        return "\n".join(lines)

    today = datetime.now(timezone.utc).astimezone().date()
    schedules = workbench_service.list_schedules_by_day(db, company.id, user.id, today)
    if schedules:
        lines += ["", "【今日日程】"]
        for s in schedules:
            start = s.start_time.astimezone().strftime("%H:%M")
            room = f"（项目：{s.room_name}）" if s.room_name else ""
            lines.append(f"- {start} {s.title}{room}")
    else:
        lines += ["", "【今日日程】今天没有安排"]

    updates = workbench_service.list_project_updates(db, company.id, employee.id)
    if updates:
        lines += ["", "【我参与的项目（最新动态）】"]
        for u in updates:
            when = (
                u.latest_event_at.astimezone().strftime("%m-%d %H:%M")
                if u.latest_event_at
                else "暂无"
            )
            lines.append(
                f"- {u.room_name}（阶段：{u.stage_label}）：{when} "
                f"{u.latest_event_author or ''} {u.latest_event_content or '暂无事件'}"
            )

    summary = workbench_service.task_summary(db, company.id, employee.id)
    lines += [
        "",
        "【我的任务】"
        f"待办 {summary.todo} · 进行中 {summary.in_progress} · 已完成 {summary.done} · 逾期 {summary.overdue}",
    ]
    return "\n".join(lines)


TWIN_SYSTEM_PROMPT = """你是 {user_name} 的 AI 数字分身（{twin_display}），服务对象是本人与其同事。

你可以依据的信息：下方【本人信息】【今日日程】【我参与的项目】【我的任务】，
以及企业知识库检索到的资料。

代理规则（必须遵守）：
1. 只能在已授权范围内代理；未授权事项要明说"这需要 {user_name} 本人确认"；
2. 不得代发正式业务回复，不得承诺时间/金额/报价/交期，除非明确已授权；
3. 普通聊天不生成任务；只有明确工作指令才生成任务；
4. 模糊、信息不足的事项，明确说明已记录为"待本人确认"，不要替本人做决定；
5. 使用简体中文，简洁、专业、条理清晰。

当前代理模式：{mode_desc}
"""


def _mode_description(twin_status: str, human_status: str) -> str:
    if twin_status == AITwinStatus.OFF.value:
        return "AI 分身已关闭：只能做通用问答，不能代表本人回应、汇报状态或接收事项。"
    if twin_status == AITwinStatus.ASSIST.value:
        return "仅辅助：可代表本人回答授权范围内的信息、接收工作事项，但不会自动创建任务。"
    return "开启代理：可在授权范围内代替本人回应、接收事项，并自动创建明确的工作任务。"


async def _stream_answer(
    company_id: str,
    system_prompt: str,
    history: list[dict],
    question: str,
    sources_bag: list[dict],
    use_knowledge: bool,
    model_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """流式生成回答（可选企业知识检索增强）。"""
    model = get_chat_model(model_id)
    messages: list = [SystemMessage(content=system_prompt)]
    for m in history:
        if m.get("role") == "user":
            messages.append(HumanMessage(content=m["content"]))
        elif m.get("role") == "assistant":
            messages.append(AIMessage(content=m["content"]))

    # 构造本次提问的人消息：把「检索资料」与「问题」放进**同一条** HumanMessage。
    # 注意：不能把"资料包"和"裸问题"拆成两条消息——最后一条若是裸问题，
    # 小模型（如 qwen2.5:3b）会忽略前一条里的资料，转而用通用知识作答。
    knowledge_block = ""
    if use_knowledge:
        try:
            results = rag_service.search(company_id, question, k=4)
            if results:
                context = "\n\n".join(
                    f"【{meta.get('source', '未知文档')}】\n{text}" for text, meta in results
                )
                for _, meta in results:
                    sources_bag.append(
                        {
                            "document_id": meta.get("document_id"),
                            "name": meta.get("source", "未知文档"),
                            "score": round(meta.get("score", 0.0), 3),
                        }
                    )
                knowledge_block = f"【企业知识库资料】\n{context}\n\n"
            else:
                # 检索不到时不许虚构（T04.8）
                knowledge_block = (
                    "【企业知识库检索结果】未检索到相关资料。\n"
                    "若用户的问题需要企业内部信息，请明确回复：当前企业知识库中未检索到足够信息，"
                    "并建议在 Knowledge 模块上传相关文档；若是与知识库无关的通用问题，直接回答。\n\n"
                )
        except Exception:  # noqa: BLE001
            logger.warning("工作台知识检索失败，忽略", exc_info=True)

    messages.append(HumanMessage(content=f"{knowledge_block}【问题】\n{question}"))

    async for chunk in model.astream(messages):
        content = chunk.content
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(b.get("text", "") for b in content if isinstance(b, dict))
        if text:
            yield _sse({"type": "token", "content": text})


async def stream_workbench_answer(
    db: Session,
    company,
    user,
    employee: Employee | None,
    history: list[dict],
    question: str,
    conversation_id: str | None = None,
    room_id: str | None = None,
    model_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """AI 工作台对话入口（SSE）。

    事件：status / intent / token / sources / task_proposals / task_created
    / ai_items / done / error。
    """
    permissions = (
        employee.effective_permissions()
        if employee
        else dict(DEFAULT_DELEGATION_PERMISSIONS)
    )
    twin_status = (
        employee.ai_twin_status.value
        if employee and hasattr(employee.ai_twin_status, "value")
        else (employee.ai_twin_status if employee else AITwinStatus.ASSIST.value)
    )
    human_status = (
        employee.status.value
        if employee and hasattr(employee.status, "value")
        else (employee.status if employee else EmployeeStatus.ONLINE.value)
    )
    try:
        twin_display = (
            employee.ai_twin_display_name if employee else f"{user.name} · AI分身"
        )
    except Exception:  # noqa: BLE001
        # 会话已关闭导致关系属性不可用时的兜底，避免流式响应直接中断
        twin_display = f"{user.name} · AI分身"

    intent = classify_twin_intent(question)
    yield _sse({"type": "status", "content": "正在理解你的工作上下文…"})
    yield _sse({"type": "intent", "intent": intent})

    # ---------- 权限边界判定 ----------
    high_risk = needs_high_risk_permission(question)
    denied_reason: str | None = None
    if twin_status == AITwinStatus.OFF.value and intent in (INTENT_ACTION, INTENT_FOLLOW_UP):
        denied_reason = "AI 分身已关闭，不能代表你接收或创建工作事项。请本人处理，或先开启 AI 分身。"
    elif high_risk and not (
        permissions.get("send_formal_reply") and permissions.get("commit_time_or_money")
    ):
        denied_reason = (
            "这涉及对外正式回复或承诺时间/金额，属于未授权范围，"
            f"AI 分身不能代替 {user.name} 做出承诺，已记录为待本人确认。"
        )

    system_prompt = TWIN_SYSTEM_PROMPT.format(
        user_name=user.name,
        twin_display=twin_display,
        mode_desc=_mode_description(twin_status, human_status),
    )
    system_prompt += "\n\n" + build_workbench_context_block(db, company, user, employee)

    if room_id:
        system_prompt += (
            "\n\n【关联项目上下文】用户当前正在查看某个项目（room_id="
            f"{room_id}），回答时优先结合该项目的阶段、成员、文档与工作事件背景。"
        )

    if denied_reason:
        system_prompt += (
            "\n\n【本次请求的限制】\n"
            f"{denied_reason}\n"
            "请在回答开头明确说明该限制，不要替本人做出任何承诺或创建任务。"
        )
    elif intent == INTENT_ACTION and twin_status == AITwinStatus.AGENT.value:
        if permissions.get("create_task"):
            system_prompt += (
                "\n\n【本次请求】识别到明确工作指令，系统已自动创建 Task，"
                "请在回答中说明创建的任务标题与负责人/截止时间（不要说还需要确认）。"
            )
        else:
            system_prompt += (
                "\n\n【本次请求】识别到明确工作指令，但未授权自动创建 Task，"
                "请说明需要本人或授权后创建。"
            )
    elif intent == INTENT_AMBIGUOUS:
        system_prompt += (
            "\n\n【本次请求】信息不足、需要本人判断，已记录为待本人确认事项，"
            "请在回答中说明需要本人确认的点。"
        )

    # ---------- 生成回答 ----------
    sources_bag: list[dict] = []
    tokens: list[str] = []

    async def _pump():
        async for evt in _stream_answer(
            company.id,
            system_prompt,
            history,
            question,
            sources_bag,
            # AI 助手是「用户主动使用」的能力，检索企业知识库不应受 AI 分身
            # 对外代理权限门控（T04.6 已明确「AI 助手 ≠ AI 分身」）。
            # 那些权限只在「AI 分身代表本人在外部沟通中回应」时才生效。
            use_knowledge=True,
            model_id=model_id,
        ):
            yield evt

    # 先落库（任务/活动），再流式输出，保证前端看到的顺序与事实一致
    created_events: list[dict] = []
    if employee is not None and not denied_reason:
        if intent == INTENT_ACTION and twin_status == AITwinStatus.AGENT.value:
            if permissions.get("create_task"):
                _, proposals = await project_agent_service.detect_and_extract(
                    question, {"member_names": []}
                )
                created = []
                for proposal in proposals:
                    task = task_service.create_company_task(
                        db,
                        company_id=company.id,
                        data=_proposal_to_create(proposal, employee.id),
                        created_by=user.id,
                        source=TaskSource.AI_TWIN,
                        source_quote=proposal.source_quote,
                    )
                    activity = workbench_service.record_activity(
                        db,
                        company.id,
                        employee.id,
                        AIActivityType.TASK_CREATED,
                        title=f"AI 分身创建任务：{task.title}",
                        content=proposal.source_quote,
                        counterparty="AI 数字分身",
                        room_id=task.room_id,
                        task_id=task.id,
                    )
                    created.append(task)
                    created_events.append(
                        {"type": "created", "task": _task_brief(task), "activity": activity.id}
                    )
                if created:
                    yield _sse({"type": "task_created", "tasks": [_task_brief(t) for t in created]})
            elif permissions.get("receive_work_items"):
                activity = workbench_service.record_activity(
                    db,
                    company.id,
                    employee.id,
                    AIActivityType.RECEIVED,
                    title=f"AI 分身接收事项：{question[:40]}",
                    content=question,
                    counterparty="AI 数字分身",
                )
                created_events.append({"type": "received", "activity": activity.id})
        elif intent == INTENT_AMBIGUOUS and permissions.get("receive_work_items"):
            activity = workbench_service.record_activity(
                db,
                company.id,
                employee.id,
                AIActivityType.NEED_CONFIRM,
                title=f"待本人确认：{question[:40]}",
                content=question,
                counterparty="AI 数字分身",
            )
            created_events.append({"type": "need_confirm", "activity": activity.id})
        elif intent == INTENT_FOLLOW_UP and twin_status != AITwinStatus.OFF.value:
            activity = workbench_service.record_activity(
                db,
                company.id,
                employee.id,
                AIActivityType.NEED_CONFIRM,
                title=f"跟进事项待确认：{question[:40]}",
                content=question,
                counterparty="AI 数字分身",
            )
            created_events.append({"type": "need_confirm", "activity": activity.id})

    async for evt in _pump():
        if evt.startswith('data: {"type": "token"'):
            try:
                tokens.append(json.loads(evt[6:])["content"])
            except Exception:  # noqa: BLE001
                pass
        yield evt

    # 代处理记录：用户主动与 AI 助手的问答不属于 AI 分身行为，不记录（T04.6）
    if denied_reason and employee is not None:
        workbench_service.record_activity(
            db,
            company.id,
            employee.id,
            AIActivityType.NEED_CONFIRM,
            title=f"超出代理权限，待本人确认：{question[:40]}",
            content=f"{denied_reason}\n原文：{question}",
            counterparty="AI 数字分身",
        )

    if sources_bag:
        seen: set = set()
        deduped: list[dict] = []
        for s in sources_bag:
            key = s.get("document_id") or s.get("name")
            if key and key not in seen:
                seen.add(key)
                deduped.append(s)
        yield _sse({"type": "sources", "sources": deduped})

    if created_events:
        yield _sse({"type": "ai_items", "items": created_events})

    # 最近对话记录（会话记录 ≠ 长期记忆）
    try:
        answer = "".join(tokens)
        conversation = conversation_service.ensure_conversation(
            db,
            company.id,
            user.id,
            conversation_id,
            kind="GENERAL",
            room_id=room_id,
            title=question[:60] or "新的对话",
        )
        conversation_service.append_message(db, conversation, "user", question)
        if answer:
            conversation_service.append_message(db, conversation, "assistant", answer)
        yield _sse({"type": "conversation", "conversation_id": conversation.id})
    except Exception:  # noqa: BLE001
        logger.warning("最近对话记录失败", exc_info=True)

    yield _sse({"type": "done"})


def _proposal_to_create(
    proposal: TaskProposal, assignee_employee_id: str | None = None
) -> TaskCreate:
    """AI 分身接收的工作要求默认落到本人名下（可再改派）。"""
    return TaskCreate(
        title=proposal.title,
        description=proposal.description,
        assignee_employee_id=assignee_employee_id,
        due_date=proposal.due_date,
        status="TODO",
    )


def _task_brief(task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status.value if hasattr(task.status, "value") else str(task.status),
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "source": task.source.value if hasattr(task.source, "value") else str(task.source),
        "room_id": task.room_id,
    }
