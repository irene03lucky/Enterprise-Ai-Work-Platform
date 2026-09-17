"""Project Agent：理解项目上下文的 AI 代理（T04）。

与 Knowledge Agent（面向企业知识库）不同，Project Agent 面向「项目」：
它能调用项目基本信息、Project Room 上下文、Work Event / Timeline、
关联 Knowledge 文档与 Task，支持：

- 项目状态总结
- 最近变化总结
- 风险识别
- 待处理事项（Task）查询
- 识别对话中的行动事项，生成 Task 提案（**不自动创建，需人工确认**）

AI 代理边界（本轮）：
✓ 查询项目信息 / 总结项目 / 识别行动事项 / 建议或创建（经确认）Task
✗ 自动替员工做业务决策 / 自动对外承诺 / 自动修改项目关键状态 / 自动发送外部通知

实现说明：
- 本地小模型（如 qwen2.5:1.5b）tool-calling 不稳定，会自动走
  「结构化上下文 + 意图识别 + 流式生成」的确定性链路；
- 模型支持 tool-calling（AGENT_MODE=always 或大模型）时，
  走 LangGraph ReAct Agent，工具包括项目概览/最近变化/任务/知识检索/任务提案。
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from app.ai.llm import get_chat_model
from app.core.config import settings
from app.models import Room, TaskStatus
from app.services import agent_service, rag_service, room_service, task_service
from app.schemas.task import TaskProposal

logger = logging.getLogger(__name__)

# ---------- 意图 ----------

INTENT_QUERY = "QUERY"  # 信息查询：只回答，不生成任务
INTENT_ACTION = "ACTION"  # 明确行动要求：生成任务提案
INTENT_FOLLOW_UP = "FOLLOW_UP"  # 后续跟进：生成跟进事项提案

# 行动动词（出现在句子中，说明要「做某件事」）
ACTION_VERBS = (
    "完成", "跟进", "整理", "准备", "提交", "确认", "修复", "上线", "测试",
    "评审", "发送", "联系", "安排", "推进", "处理", "修改", "更新", "输出",
    "编写", "交付", "核对", "汇总", "调研", "对接", "优化", "补齐", "排查",
    "评估", "报价", "排期", "验收",
)
# 祈使/指派标记
IMPERATIVE_MARKERS = ("让", "请", "安排", "指派", "记得", "提醒", "需要", "帮我", "@")
# 跟进标记（「以后告诉我」这类）
FOLLOW_UP_MARKERS = (
    "以后告诉我", "之后告诉我", "后告诉我", "告诉我", "提醒我", "到时候",
    "上线后", "上线以后", "上线之后", "有进展", "持续关注", "记得跟进", "跟进一下",
)
# 明确提问（查询）标记
QUERY_MARKERS = (
    "怎么样", "如何", "什么", "哪些", "总结", "风险", "进展", "状态", "情况",
    "吗", "呢", "？", "?",
)

_WEEKDAY_MAP = {
    "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6,
    "1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6,
}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


# ---------- 项目上下文构建 ----------


def build_project_context(
    db: Session,
    room: Room,
    current_employee_id: str | None = None,
    recent_limit: int = 20,
    access_level: str = room_service.ACCESS_MEMBER,
) -> dict:
    """汇总项目上下文：基本信息 / 阶段 / 成员 / 关联文档 / Timeline / Task。

    access_level=related 时只汇总公开里程碑（其他部门同事视角）。
    """
    members = room_service.list_members(db, room.id)
    documents = room_service.list_room_documents(db, room.id)
    events = room_service.list_events(
        db, room.id, limit=recent_limit, access_level=access_level
    )
    tasks = task_service.list_room_tasks(db, room.id)
    summary = task_service.summarize_room_tasks(db, room.id)

    member_lines: list[str] = []
    member_names: list[str] = []
    for m in members:
        emp = m.employee
        if emp is None:
            continue
        name = emp.user.name if emp.user else "未知"
        member_names.append(name)
        dept = emp.department.name if emp.department else "未分配部门"
        role_part = " · 负责人" if m.role == "OWNER" else ""
        member_lines.append(
            f"- {name}（{dept}"
            + (f"·{emp.position}" if emp.position else "")
            + f"{role_part}）"
        )

    doc_lines = [
        f"- {d.document.name}（{d.document.chunk_count} 个知识块）"
        for d in documents
        if d.document
    ]

    event_lines: list[str] = []
    for e in reversed(events):  # 时间正序，便于阅读
        author = e.employee.user.name if e.employee and e.employee.user else "未知"
        when = e.event_date.strftime("%Y-%m-%d %H:%M") if e.event_date else ""
        etype = e.type.value if hasattr(e.type, "value") else str(e.type)
        event_lines.append(f"[{when}][{etype}] {author}: {e.content[:400]}")

    def _task_line(t) -> str:
        assignee = t.assignee.user.name if t.assignee and t.assignee.user else "未指派"
        due = f"，截止 {t.due_date}" if t.due_date else ""
        status = (
            "待办" if t.status == TaskStatus.TODO
            else "进行中" if t.status == TaskStatus.IN_PROGRESS
            else "已完成"
        )
        return f"- [{status}] {t.title}（负责人：{assignee}{due}）"

    open_tasks = [t for t in tasks if t.status != TaskStatus.DONE]
    done_tasks = [t for t in tasks if t.status == TaskStatus.DONE]
    my_tasks = [t for t in tasks if current_employee_id and t.assignee_employee_id == current_employee_id]

    return {
        "room_id": room.id,
        "company_id": room.company_id,
        "name": room.name,
        "status": room.status.value if hasattr(room.status, "value") else str(room.status),
        "stage": room.stage.value if hasattr(room.stage, "value") else str(room.stage),
        "access_level": access_level,
        "description": room.description,
        "member_lines": member_lines,
        "member_names": member_names,
        "document_lines": doc_lines,
        "document_ids": [d.document_id for d in documents],
        "event_lines": event_lines,
        "events_raw": events,
        "task_lines": [_task_line(t) for t in tasks],
        "open_task_lines": [_task_line(t) for t in open_tasks],
        "my_task_lines": [_task_line(t) for t in my_tasks],
        "done_task_lines": [_task_line(t) for t in done_tasks],
        "task_summary": summary,
        "tasks_raw": tasks,
    }


def format_project_context(ctx: dict) -> str:
    """把项目上下文格式化为提示词块。"""
    summary = ctx.get("task_summary", {})
    lines = [
        "【项目信息】",
        f"名称：{ctx.get('name', '未知项目')}",
        f"状态：{ctx.get('status', '未知')}",
        f"当前阶段：{ctx.get('stage', '未设置')}",
        f"简介：{ctx.get('description') or '暂无'}",
        "",
        f"【项目成员】（{len(ctx.get('member_lines', []))} 人）",
        *(ctx.get("member_lines") or ["暂无成员"]),
        "",
        "【关联文档】",
        *(ctx.get("document_lines") or ["暂无关联文档"]),
        "",
        "【最近工作事件（Timeline，时间正序）】",
        *(ctx.get("event_lines") or ["暂无事件记录"]),
        "",
        "【项目任务】",
        f"统计：待办 {summary.get('todo', 0)} · 进行中 {summary.get('in_progress', 0)}"
        f" · 已完成 {summary.get('done', 0)} · 逾期 {summary.get('overdue', 0)}",
        *(ctx.get("open_task_lines") or ["暂无未完成任务"]),
    ]
    if ctx.get("my_task_lines"):
        lines += ["", "【当前用户的任务】", *ctx["my_task_lines"]]
    if ctx.get("done_task_lines"):
        lines += ["", "【已完成任务】", *ctx["done_task_lines"][:10]]
    return "\n".join(lines)


# ---------- 意图识别与任务抽取 ----------


def _parse_due_date(text: str, today: date | None = None) -> date | None:
    """从中文表达中解析截止日期：今天/明天/后天/周X/下周X/X月X日/YYYY-MM-DD。"""
    today = today or date.today()
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", text)
    if m:
        try:
            candidate = date(today.year, int(m.group(1)), int(m.group(2)))
            # 跨年：若已早于今天超过半年，视为明年
            if candidate < today - timedelta(days=180):
                candidate = date(today.year + 1, int(m.group(1)), int(m.group(2)))
            return candidate
        except ValueError:
            pass

    if "后天" in text:
        return today + timedelta(days=2)
    if "明天" in text or "明日" in text:
        return today + timedelta(days=1)
    if "今天" in text or "今日" in text:
        return today

    m = re.search(r"(本\s*周|这\s*周|下\s*周|本\s*星期|下\s*星期)?\s*(?:周|星期)\s*([一二三四五六日天1-7])", text)
    if m:
        target = _WEEKDAY_MAP.get(m.group(2))
        if target is not None:
            delta = (target - today.weekday()) % 7
            prefix = (m.group(1) or "").replace(" ", "")
            if prefix.startswith("下"):
                delta += 7
            elif not prefix and delta == 0:
                delta = 0
            return today + timedelta(days=delta)
    return None


def _has_person_reference(text: str) -> bool:
    """是否指明了执行人（让李四/请张三/@王五）。"""
    return bool(
        re.search(r"[让请指派]\s*[\u4e00-\u9fa5A-Za-z]{1,6}", text)
        or re.search(r"@\s*[\u4e00-\u9fa5A-Za-z]{1,10}", text)
    )


def classify_intent(question: str) -> str:
    """规则优先的意图识别（避免把普通聊天转成任务）。"""
    text = question.strip()
    has_verb = any(v in text for v in ACTION_VERBS)
    has_imperative = any(m in text for m in IMPERATIVE_MARKERS)
    is_follow_up = any(m in text for m in FOLLOW_UP_MARKERS)
    has_person = _has_person_reference(text)
    has_time = _parse_due_date(text) is not None or bool(
        re.search(r"(周[一二三四五六日天]|星期[一二三四五六日天]|月底|前)", text)
    )

    # 明确指派/祈使 + 行动或时间 → 行动要求
    if has_imperative and (has_verb or has_time) and (has_person or has_verb):
        # 「告诉我/提醒我」且未指派他人 → 跟进事项
        if is_follow_up and not has_person:
            return INTENT_FOLLOW_UP
        return INTENT_ACTION
    if has_verb and (has_person or has_time):
        if is_follow_up and not has_person:
            return INTENT_FOLLOW_UP
        return INTENT_ACTION
    if is_follow_up:
        return INTENT_FOLLOW_UP

    # 纯查询（含疑问句、要求总结/风险/进展）
    if any(q in text for q in QUERY_MARKERS) or not has_verb:
        return INTENT_QUERY
    return INTENT_QUERY


# 姓名右边界：时间词、动作动词首字、标点或空白（用于「让李四周五前完成测试」→ 李四）
_VERB_START_CHARS = "".join(sorted({v[0] for v in ACTION_VERBS}))
_NAME_RIGHT_BOUNDARY = (
    r"(?=[\s，。、；;!！?？]|[在明日周今本下\d" + _VERB_START_CHARS + r"])"
)


def _extract_assignee_name(text: str, member_names: list[str] | None = None) -> str | None:
    """抽取负责人：优先匹配项目成员姓名，其次按「让/请/指派 X」的规则截取。"""
    for name in sorted((member_names or []), key=len, reverse=True):
        if name and name in text:
            return name
    m = re.search(
        r"[让请指派]\s*([\u4e00-\u9fa5A-Za-z]{1,4}?)" + _NAME_RIGHT_BOUNDARY, text
    )
    if m:
        return m.group(1)
    m = re.search(r"@\s*([\u4e00-\u9fa5A-Za-z]{1,10})", text)
    if m:
        return m.group(1)
    return None


def _heuristic_proposal(question: str, intent: str, ctx: dict | None = None) -> TaskProposal:
    """规则兜底的任务抽取（确定性，小模型或 LLM 输出不合法时使用）。"""
    text = question.strip()
    title = re.sub(
        r"^(帮我|麻烦|请|需要|要|记得|提醒我|提醒|让|安排|指派)\s*", "", text
    )
    title = re.split(r"[，。；;！!？?\n]", title)[0].strip()
    if intent == INTENT_FOLLOW_UP:
        title = f"跟进：{title}" if not title.startswith("跟进") else title
    if not title:
        title = text[:60]
    title = title[:60]

    assignee = _extract_assignee_name(text, (ctx or {}).get("member_names"))

    return TaskProposal(
        title=title,
        description=None,
        assignee_name=assignee,
        due_date=_parse_due_date(text),
        source="FOLLOW_UP" if intent == INTENT_FOLLOW_UP else "CHAT",
        source_quote=text[:400],
    )


def _extract_json_payload(text: str) -> dict | list | None:
    """从模型输出中提取第一个 JSON 对象/数组（容忍 ```json 与前后废话）。"""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


EXTRACT_PROMPT = """你是企业项目管理助手。判断用户消息是否包含「明确的行动要求」或「后续跟进事项」，并抽取为任务。

只输出 JSON，不要任何解释，格式：
{{"tasks":[{{"title":"动词开头的可执行任务标题，不超过30字","description":"补充说明或空字符串","assignee_name":"负责人姓名或空字符串","due_date":"YYYY-MM-DD或空字符串","source_quote":"原文关键句"}}]}}

规则：
1. 纯信息查询（如「项目现在怎么样」「最近有什么变化」「有哪些风险」「谁负责什么」）输出 {{"tasks":[]}}；
2.「让李四周五前完成测试」这类明确指派属于行动要求，抽取为任务；
3.「上线以后告诉我」「有进展提醒我」属于后续跟进，title 以「跟进：」开头；
4. due_date 只能输出 YYYY-MM-DD，无法确定时输出空字符串；
5. 不要编造负责人和时间，消息里没有就留空。

今天日期：{today}
项目成员：{members}
用户消息：{question}"""


async def _llm_extract_proposals(
    question: str, ctx: dict, intent: str
) -> list[TaskProposal]:
    """用 LLM 抽取结构化任务信息；失败时回退规则抽取。"""
    prompt = EXTRACT_PROMPT.format(
        today=date.today().isoformat(),
        members="、".join(ctx.get("member_names") or []) or "（暂无成员信息）",
        question=question[:800],
    )
    try:
        model = get_chat_model()
        resp = await asyncio.wait_for(
            model.ainvoke([HumanMessage(content=prompt)]), timeout=60
        )
        content = resp.content if isinstance(resp.content, str) else "".join(
            b.get("text", "") for b in resp.content if isinstance(b, dict)
        )
        payload = _extract_json_payload(content)
        if isinstance(payload, dict):
            payload = payload.get("tasks")
        if not isinstance(payload, list):
            return []
        proposals: list[TaskProposal] = []
        for item in payload[:5]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            due_raw = str(item.get("due_date") or "").strip()
            due = None
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_raw):
                try:
                    due = date.fromisoformat(due_raw)
                except ValueError:
                    due = None
            if due is None:
                due = _parse_due_date(f"{question} {due_raw}")
            proposals.append(
                TaskProposal(
                    title=title[:60],
                    description=(str(item.get("description") or "").strip() or None),
                    assignee_name=(str(item.get("assignee_name") or "").strip() or None),
                    due_date=due,
                    source="FOLLOW_UP" if intent == INTENT_FOLLOW_UP else "CHAT",
                    source_quote=(str(item.get("source_quote") or "").strip() or question[:400]),
                )
            )
        return proposals
    except Exception:  # noqa: BLE001
        logger.warning("LLM 任务抽取失败，回退规则抽取", exc_info=True)
        return []


# 模型把提示词模板当内容输出时的特征词（出现即判定为脏数据）
_TEMPLATE_JUNK = (
    "或空字符串", "YYYY", "{{", "}}", "今天日期", "项目成员", "用户消息", "不超过30字",
)


def _sanitize_proposal(
    proposal: TaskProposal, question: str, ctx: dict
) -> TaskProposal | None:
    """校验 LLM 抽取结果：过滤模板泄漏、幻觉负责人与越界日期。"""
    title = (proposal.title or "").strip()
    if not title or len(title) < 2:
        return None
    if any(junk in title for junk in _TEMPLATE_JUNK):
        return None

    description = proposal.description
    if description and any(junk in description for junk in _TEMPLATE_JUNK):
        description = None

    quote = proposal.source_quote
    if quote and any(junk in quote for junk in ("今天日期", "项目成员", "用户消息")):
        quote = question[:400]

    # 负责人：必须在用户原话中出现，或是项目成员之一（防止模型幻觉）
    assignee = proposal.assignee_name
    if assignee and assignee not in question and assignee not in (ctx.get("member_names") or []):
        assignee = None

    # 截止日期：优先相信对原文的规则解析，其次校验模型给出的日期是否落在合理范围
    due = _parse_due_date(question)
    if due is None and proposal.due_date is not None:
        today = date.today()
        if today <= proposal.due_date <= today + timedelta(days=365):
            due = proposal.due_date

    return TaskProposal(
        title=title[:60],
        description=description,
        assignee_name=assignee,
        due_date=due,
        source=proposal.source,
        source_quote=quote,
    )


async def detect_and_extract(
    question: str, ctx: dict
) -> tuple[str, list[TaskProposal]]:
    """意图识别 + 任务抽取。

    策略：
    - 意图由规则把关（普通聊天绝不生成任务）；
    - 小模型 tool-calling / 结构化输出不可靠，直接用规则抽取（确定性）；
    - 能力足够的模型走 LLM 结构化抽取，但仍需通过 _sanitize_proposal 校验，
      校验不通过时回落规则抽取。
    """
    intent = classify_intent(question)
    if intent == INTENT_QUERY:
        return INTENT_QUERY, []

    if agent_service.supports_tool_calling():
        try:
            raw = await _llm_extract_proposals(question, ctx, intent)
            proposals = [p for p in (_sanitize_proposal(x, question, ctx) for x in raw) if p]
            if proposals:
                return intent, proposals
        except Exception:  # noqa: BLE001
            logger.warning("LLM 抽取异常，回退规则抽取", exc_info=True)

    return intent, [_heuristic_proposal(question, intent, ctx)]


# ---------- 提示词 ----------

PROJECT_AGENT_SYSTEM_PROMPT = """你是「{room_name}」项目的 Project Agent，服务对象是项目成员。

你可以依据的信息只有两类：
1. 下面给出的项目上下文（项目信息、成员、关联文档、工作事件 Timeline、任务）；
2. 用户消息中附带的企业知识库检索片段（如有）。

能力：
- 项目状态总结：整体进展、当前阶段、关键决策；
- 最近变化总结：依据 Timeline 归纳最近发生了什么，注明时间；
- 风险识别：从客户反馈、逾期任务、阻塞事项中识别风险，并说明依据；
- 待处理事项：列出未完成任务（待办/进行中/逾期）。

回答要求：
- 使用简体中文，简洁、专业、条理清晰，适当使用列表；
- 结论必须来自上下文，上下文没有的信息如实说明「项目记录中没有相关信息」，不要编造；
- 涉及时间时写明事件时间或任务截止日期。
"""

BOUNDARY_RULES = """
AI 代理边界（必须遵守）：
- 只能查询、总结、识别行动事项并「建议」任务；
- 不得替员工做业务决策，不得代表团队对外承诺（如承诺交付时间、报价）；
- 不得修改项目关键状态（如把项目标记为已完成）；
- 不得代发外部通知；
- 涉及具体行动的任务，只提交提案，等待用户在界面上确认后创建。
"""

ACTION_INSTRUCTION = """
本轮用户在对话中提出了明确的行动要求。系统已从原话抽取到以下任务信息
（**以它为准，不要自行修改负责人与时间，也不要替换为项目中的其他人**）：
{facts}

请：
1. 先用 1-2 句话确认你对任务的理解（做什么、谁负责、什么时候前）；
2. 明确提示用户：已生成任务提案，请在下方确认卡片中确认后创建为 Task；
3. 不要说「已经创建」。
"""

FOLLOW_UP_INSTRUCTION = """
本轮用户提出了后续跟进事项（例如「上线以后告诉我」）。系统已抽取到以下跟进信息
（**以它为准，不要自行修改**）：
{facts}

请：
1. 用 1-2 句话说明跟进点与触发时机；
2. 明确提示用户：已生成跟进事项提案，请确认后创建为 Task；
3. 不要说「已经创建」。
"""


# ---------- LangGraph Agent（模型支持 tool-calling 时） ----------


def _make_project_tools(
    db: Session,
    company_id: str,
    room_id: str,
    ctx: dict,
    proposals_bag: list[TaskProposal],
    sources_bag: list[dict],
):
    """构造 Project Agent 工具集（闭包绑定项目与会话）。"""

    @tool
    def get_project_overview() -> str:
        """获取项目基本信息、成员、关联文档与任务统计概览。"""
        summary = ctx.get("task_summary", {})
        return "\n".join(
            [
                f"项目：{ctx.get('name')}（状态 {ctx.get('status')}）",
                f"简介：{ctx.get('description') or '暂无'}",
                "成员：" + ("、".join(ctx.get("member_names") or []) or "暂无"),
                "关联文档：" + ("；".join(ctx.get("document_lines") or []) or "暂无"),
                "任务统计："
                f"待办 {summary.get('todo', 0)} / 进行中 {summary.get('in_progress', 0)}"
                f" / 已完成 {summary.get('done', 0)} / 逾期 {summary.get('overdue', 0)}",
            ]
        )

    @tool
    def get_recent_changes(days: int = 7) -> str:
        """获取最近 N 天的工作事件变化（Timeline）。默认 7 天。"""
        since = datetime.utcnow() - timedelta(days=max(1, min(int(days or 7), 365)))
        lines: list[str] = []
        for e in reversed(ctx.get("events_raw") or []):
            when = e.event_date or e.created_at
            if when is not None:
                event_time = when.replace(tzinfo=None) if when.tzinfo else when
                if event_time < since:
                    continue
            author = e.employee.user.name if e.employee and e.employee.user else "未知"
            etype = e.type.value if hasattr(e.type, "value") else str(e.type)
            stamp = e.event_date.strftime("%Y-%m-%d %H:%M") if e.event_date else ""
            lines.append(f"[{stamp}][{etype}] {author}: {e.content[:400]}")
        return "\n".join(lines) if lines else f"最近 {days} 天没有新的工作事件。"

    @tool
    def get_project_tasks(status: str = "OPEN") -> str:
        """查询项目任务。status 取值：OPEN（未完成，默认）/ TODO / IN_PROGRESS / DONE / ALL。"""
        wanted = (status or "OPEN").upper()
        tasks = ctx.get("tasks_raw") or []
        if wanted == "OPEN":
            picked = [t for t in tasks if t.status != TaskStatus.DONE]
        elif wanted == "ALL":
            picked = list(tasks)
        else:
            picked = [t for t in tasks if getattr(t.status, "value", str(t.status)) == wanted]
        if not picked:
            return "没有符合条件的任务。"
        lines = []
        for t in picked:
            assignee = t.assignee.user.name if t.assignee and t.assignee.user else "未指派"
            due = f"，截止 {t.due_date}" if t.due_date else ""
            state = getattr(t.status, "value", str(t.status))
            lines.append(f"[{state}] {t.title}（负责人：{assignee}{due}）")
        return "\n".join(lines)

    @tool
    def search_project_knowledge(query: str) -> str:
        """检索项目关联的知识文档（企业知识库范围内）。"""
        results = rag_service.search(company_id, query, k=4, document_ids=ctx.get("document_ids") or None)
        if not results:
            return "项目关联文档中没有检索到相关内容。"
        formatted = []
        for i, (text, meta) in enumerate(results, start=1):
            source_name = meta.get("source", "未知文档")
            formatted.append(f"[{i}] 来源：{source_name}\n{text}")
            sources_bag.append(
                {
                    "document_id": meta.get("document_id"),
                    "name": source_name,
                    "score": round(meta.get("score", 0.0), 3),
                }
            )
        return "\n\n".join(formatted)

    @tool
    def propose_task(
        title: str,
        description: str = "",
        assignee_name: str = "",
        due_date: str = "",
        source_quote: str = "",
    ) -> str:
        """当用户提出明确行动要求或后续跟进事项时，提交任务提案等待人工确认。

        不要用它来做查询；不要把普通聊天内容转成任务。
        due_date 格式为 YYYY-MM-DD，无法确定时留空。
        """
        parsed = None
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", (due_date or "").strip()):
            try:
                parsed = date.fromisoformat(due_date.strip())
            except ValueError:
                parsed = None
        proposals_bag.append(
            TaskProposal(
                title=title[:60],
                description=(description or "").strip() or None,
                assignee_name=(assignee_name or "").strip() or None,
                due_date=parsed,
                source="CHAT",
                source_quote=(source_quote or "").strip() or None,
            )
        )
        return "已生成任务提案，等待用户在界面上确认后创建（你不需要也不能直接创建任务）。"

    return [
        get_project_overview,
        get_recent_changes,
        get_project_tasks,
        search_project_knowledge,
        propose_task,
    ]


async def _stream_agent(
    ctx: dict,
    db: Session,
    history: list[dict],
    question: str,
    system_prompt: str,
    proposals_bag: list[TaskProposal],
    sources_bag: list[dict],
    thread_id: str | None = None,
    model_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """LangGraph ReAct Agent 路径（要求模型支持 tool-calling）。"""
    model = get_chat_model(model_id)
    tools = _make_project_tools(
        db, ctx["company_id"], ctx["room_id"], ctx, proposals_bag, sources_bag
    )
    agent = create_react_agent(
        model=model, tools=tools, checkpointer=agent_service.get_checkpointer()
    )
    messages: list = [SystemMessage(content=system_prompt)]
    # 服务端记忆（MemorySaver）：thread_id 存在时信任 Checkpointer 状态，避免历史重复注入
    if thread_id is None:
        for m in history:
            if m.get("role") == "user":
                messages.append(HumanMessage(content=m["content"]))
            elif m.get("role") == "assistant":
                messages.append(AIMessage(content=m["content"]))
    messages.append(HumanMessage(content=question))

    config: dict = {"recursion_limit": 30}
    if thread_id:
        config["configurable"] = {"thread_id": thread_id}

    emitted = False
    async for event in agent.astream_events(
        {"messages": messages}, version="v2", config=config
    ):
        if event["event"] == "on_tool_start" and event["name"] in {
            "search_project_knowledge",
            "get_recent_changes",
            "get_project_tasks",
            "get_project_overview",
        }:
            yield _sse({"type": "status", "content": "正在读取项目上下文…"})
        elif event["event"] == "on_chat_model_stream":
            chunk = event["data"].get("chunk")
            if chunk is None:
                continue
            content = chunk.content
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "".join(b.get("text", "") for b in content if isinstance(b, dict))
            if text:
                emitted = True
                yield _sse({"type": "token", "content": text})
    if not emitted:
        raise RuntimeError("Agent 未产出内容")


async def _stream_direct(
    ctx: dict,
    company_id: str,
    history: list[dict],
    question: str,
    system_prompt: str,
    sources_bag: list[dict],
    intent: str,
    model_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """确定性链路：项目上下文 + 知识检索（仅查询意图）+ 流式生成。"""
    model = get_chat_model(model_id)
    messages: list = [SystemMessage(content=system_prompt)]
    for m in history:
        if m.get("role") == "user":
            messages.append(HumanMessage(content=m["content"]))
        elif m.get("role") == "assistant":
            messages.append(AIMessage(content=m["content"]))

    if intent == INTENT_QUERY and ctx.get("document_ids"):
        try:
            results = rag_service.search(
                company_id, question, k=4, document_ids=ctx["document_ids"]
            )
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
                messages.append(
                    HumanMessage(
                        content=(
                            "【项目关联文档检索片段】\n"
                            f"{context}\n\n【用户问题】\n{question}"
                        )
                    )
                )
        except Exception:  # noqa: BLE001
            logger.warning("项目知识检索失败，忽略", exc_info=True)

    if not messages or not isinstance(messages[-1], HumanMessage):
        messages.append(HumanMessage(content=question))

    async for chunk in model.astream(messages):
        content = chunk.content
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(b.get("text", "") for b in content if isinstance(b, dict))
        if text:
            yield _sse({"type": "token", "content": text})


def _use_agent() -> bool:
    """是否使用 LangGraph Agent 编排。"""
    mode = settings.AGENT_MODE
    if mode == "always":
        return True
    if mode == "never":
        return False
    return agent_service.supports_tool_calling()


async def stream_project_answer(
    db: Session,
    room: Room,
    history: list[dict],
    question: str,
    current_employee_id: str | None = None,
    access_level: str = room_service.ACCESS_MEMBER,
    model_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Project Agent 主入口（SSE 事件流）。

    事件类型：
    - status：阶段提示
    - intent：QUERY / ACTION / FOLLOW_UP
    - token：回答增量
    - sources：引用的项目文档
    - task_proposals：任务提案（需用户确认后创建，AI 不自动创建）
    - done / error
    """
    ctx = build_project_context(db, room, current_employee_id=current_employee_id)
    yield _sse({"type": "status", "content": "正在理解项目上下文…"})

    intent, proposals = await detect_and_extract(question, ctx)
    yield _sse({"type": "intent", "intent": intent})

    context_block = format_project_context(ctx)
    system_prompt = (
        PROJECT_AGENT_SYSTEM_PROMPT.format(room_name=ctx.get("name", "当前项目"))
        + "\n\n"
        + context_block
        + "\n"
        + BOUNDARY_RULES
    )
    # 时间锚点：LLM 无时间概念，必须显式注入（否则会编造日期）
    system_prompt += "\n" + agent_service.now_line() + "\n"
    if intent in (INTENT_ACTION, INTENT_FOLLOW_UP) and proposals:
        facts = "\n".join(
            f"- 任务：{p.title}（负责人：{p.assignee_name or '未指定'}，"
            f"截止：{p.due_date.isoformat() if p.due_date else '未指定'}）"
            for p in proposals
        )
        template = (
            ACTION_INSTRUCTION if intent == INTENT_ACTION else FOLLOW_UP_INSTRUCTION
        )
        system_prompt += template.format(facts=facts)

    sources_bag: list[dict] = []
    proposals_bag: list[TaskProposal] = list(proposals)
    # LangGraph MemorySaver 服务端记忆：按「项目 + 成员」维度持久化多轮对话状态
    thread_id = f"project:{room.id}:{current_employee_id or 'anon'}"
    try:
        if _use_agent():
            async for evt in _stream_agent(
                ctx, db, history, question, system_prompt, proposals_bag, sources_bag,
                thread_id=thread_id, model_id=model_id,
            ):
                yield evt
        else:
            async for evt in _stream_direct(
                ctx,
                room.company_id,
                history,
                question,
                system_prompt,
                sources_bag,
                intent,
                model_id=model_id,
            ):
                yield evt
    except Exception:  # noqa: BLE001
        logger.exception("Project Agent 执行异常，降级为直接生成")
        yield _sse({"type": "status", "content": "正在重新组织回答…"})
        async for evt in _stream_direct(
            ctx,
            room.company_id,
            history,
            question,
            system_prompt,
            sources_bag,
            intent,
            model_id=model_id,
        ):
            yield evt

    if sources_bag:
        seen: set = set()
        deduped: list[dict] = []
        for s in sources_bag:
            key = s.get("document_id") or s.get("name")
            if key and key not in seen:
                seen.add(key)
                deduped.append(s)
        yield _sse({"type": "sources", "sources": deduped})

    if proposals_bag:
        yield _sse(
            {
                "type": "task_proposals",
                "proposals": [p.model_dump(mode="json") for p in proposals_bag],
            }
        )
    yield _sse({"type": "done"})
