"""Knowledge Agent：LangGraph ReAct Agent + 企业知识检索工具。

用户流程：员工提问 → Agent 判断是否需要检索 → 调用 knowledge_search
Tool → Chroma 检索相关文档 → Ollama 生成回答 → 返回答案 + 来源文档。

Agent 失败时自动降级为直接 RAG 链（检索 → 生成），保证可用性。
"""

import json
import logging
import re
from collections.abc import AsyncGenerator
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.ai.llm import get_chat_model
from app.core.config import settings
from app.services import rag_service

logger = logging.getLogger(__name__)

# 进程内共享 Checkpointer（LangGraph MemorySaver）：
# 同一 thread_id 的多轮对话状态在服务端持久化，Agent 每轮自动携带完整历史与工具调用轨迹。
# 注意：MemorySaver 进程内存活，容器重启后记忆清零（会话文本仍持久化在 conversations 表）。
_checkpointer = MemorySaver()


def get_checkpointer() -> MemorySaver:
    """共享的 LangGraph 记忆 Checkpointer（Knowledge Agent / Project Agent 共用）。"""
    return _checkpointer

# 已验证无法稳定 tool-calling 的本地小模型：跳过 Agent 编排，直接 RAG
# 注：qwen2.5:3b 经实测可稳定完成单步工具调用（时间/日程），已移出本清单。
_SMALL_MODELS_WITHOUT_TOOL_CALLING = {
    "qwen2.5:0.5b",
    "qwen2.5:1.5b",
    "qwen2.5:1b",
    "llama3.2:1b",
    "llama3.2:3b",
}

SYSTEM_PROMPT_TEMPLATE = """你是「{company_name}」的企业 AI 工作助手。

当前用户：{user_name}（{department}{position_part}）

你的职责：
1. 当问题涉及公司制度、规范、产品、项目资料等企业内部信息时，必须先调用 knowledge_search 工具检索企业知识库，再基于检索结果回答；
2. 回答企业相关问题时必须以检索到的资料为依据，资料中没有的信息要明确说明"企业知识库中暂无相关资料"；
3. 与企业知识无关的通用问题可以直接回答；
4. 需要检索时必须立即调用 knowledge_search 工具，并基于工具返回的资料作答；
   严禁只回复"请稍等/正在查询"之类的过渡语而不调用工具——要么调用工具后回答，要么直接回答；
5. 使用简体中文，简洁、专业、条理清晰，适当使用列表。"""

FALLBACK_PROMPT_TEMPLATE = """请基于以下企业知识库资料回答问题。如果资料不足以回答，请明确说明。

【企业知识库资料】
{context}

【问题】
{question}
"""

RAG_SYSTEM_PROMPT = """你是企业的 AI 工作助手。请严格依据提供的【企业知识库资料】回答问题：
- 资料中没有的信息，如实说明"企业知识库中暂无相关资料"，不要编造；
- 使用简体中文，简洁、专业、条理清晰，适当使用列表；
- 涉及具体数字（金额、天数、标准）时必须与资料一致。"""


def supports_tool_calling() -> bool:
    """当前生成模型是否能稳定使用 LangGraph tool-calling Agent。

    本地小模型（≤3B）tool-calling 不可靠，会跳过检索直接作答，
    因此 auto 模式下这些模型走「先检索后生成」的确定性链路。
    """
    return not (
        settings.LLM_PROVIDER == "ollama"
        and settings.LLM_MODEL in _SMALL_MODELS_WITHOUT_TOOL_CALLING
    )


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# 常见时区中文名（未收录的时区直接显示 IANA 名称）
_TZ_LABELS = {
    "Asia/Shanghai": "北京时间",
    "Asia/Hong_Kong": "香港时间",
    "Asia/Taipei": "台北时间",
    "Asia/Tokyo": "日本时间",
    "Asia/Seoul": "韩国时间",
    "Asia/Singapore": "新加坡时间",
    "Asia/Bangkok": "曼谷时间",
    "Asia/Dubai": "迪拜时间",
    "Asia/Kolkata": "印度时间",
    "Europe/London": "伦敦时间",
    "Europe/Paris": "巴黎时间",
    "Europe/Berlin": "柏林时间",
    "Europe/Moscow": "莫斯科时间",
    "America/Los_Angeles": "洛杉矶 / 旧金山时间（美西）",
    "America/Denver": "丹佛时间（美西山区）",
    "America/Chicago": "芝加哥时间（美中）",
    "America/New_York": "纽约时间（美东）",
    "America/Sao_Paulo": "圣保罗时间（巴西）",
    "Australia/Sydney": "悉尼时间",
    "UTC": "UTC 协调世界时",
}


# 中文城市 / 地区名 → IANA 时区（未收录的城市可直接用 IANA 名查询）
_TZ_ALIASES = {
    "北京": "Asia/Shanghai",
    "上海": "Asia/Shanghai",
    "深圳": "Asia/Shanghai",
    "广州": "Asia/Shanghai",
    "中国": "Asia/Shanghai",
    "香港": "Asia/Hong_Kong",
    "台北": "Asia/Taipei",
    "台湾": "Asia/Taipei",
    "东京": "Asia/Tokyo",
    "大阪": "Asia/Tokyo",
    "日本": "Asia/Tokyo",
    "首尔": "Asia/Seoul",
    "韩国": "Asia/Seoul",
    "新加坡": "Asia/Singapore",
    "曼谷": "Asia/Bangkok",
    "泰国": "Asia/Bangkok",
    "迪拜": "Asia/Dubai",
    "阿联酋": "Asia/Dubai",
    "孟买": "Asia/Kolkata",
    "印度": "Asia/Kolkata",
    "伦敦": "Europe/London",
    "英国": "Europe/London",
    "巴黎": "Europe/Paris",
    "法国": "Europe/Paris",
    "柏林": "Europe/Berlin",
    "德国": "Europe/Berlin",
    "莫斯科": "Europe/Moscow",
    "俄罗斯": "Europe/Moscow",
    "旧金山": "America/Los_Angeles",
    "洛杉矶": "America/Los_Angeles",
    "硅谷": "America/Los_Angeles",
    "美西": "America/Los_Angeles",
    "西雅图": "America/Los_Angeles",
    "丹佛": "America/Denver",
    "芝加哥": "America/Chicago",
    "美中": "America/Chicago",
    "纽约": "America/New_York",
    "华盛顿": "America/New_York",
    "美东": "America/New_York",
    "圣保罗": "America/Sao_Paulo",
    "巴西": "America/Sao_Paulo",
    "悉尼": "Australia/Sydney",
    "澳大利亚": "Australia/Sydney",
    "utc": "UTC",
    "协调世界时": "UTC",
}


def resolve_timezone(text: str) -> tuple[str, str] | None:
    """把城市名或时区名解析为 (IANA 时区名, 中文展示名)；无法识别返回 None。

    依次尝试：① 合法的 IANA 名；② 中文城市别名；③ 在 zoneinfo 全量时区里按城市名模糊匹配。
    """
    raw = (text or "").strip()
    if not raw:
        return None

    # ① 直接是合法 IANA 名（如 America/Los_Angeles）
    try:
        ZoneInfo(raw)
        return raw, _TZ_LABELS.get(raw, raw)
    except Exception:  # noqa: BLE001
        pass

    key = raw.replace(" ", "").replace("_", "").lower()

    # ② 中文别名（精确优先，再做包含匹配）
    for alias, tz_name in _TZ_ALIASES.items():
        if alias.lower() == key:
            return tz_name, _TZ_LABELS.get(tz_name, tz_name)
    for alias, tz_name in _TZ_ALIASES.items():
        if alias.lower() in key or key in alias.lower():
            return tz_name, _TZ_LABELS.get(tz_name, tz_name)

    # ③ 英文城市名 → 在 zoneinfo 全量时区中按末段城市名匹配
    for tz_name in sorted(available_timezones()):
        city = tz_name.rsplit("/", 1)[-1].replace("_", "").lower()
        if city and (city == key or city in key):
            return tz_name, _TZ_LABELS.get(tz_name, tz_name)
    return None


def now_line() -> str:
    """当前时间锚点（多时区，必须显式注入提示词）。

    LLM 自身没有时间概念，训练数据里也没有"今天"：
    - 不注入时间 → 被问「今天是几号」会编造训练期内的日期，且被质疑后仍坚持；
    - 只注入单一时区 → 被问「洛杉矶现在几点」只能让用户自行换算。

    因此一次性给出常用时区的当前时间。时区清单由 APP_TIMEZONES 配置，
    跨境电商 / 多市场团队把业务所在时区都列上即可。
    """
    lines = [
        "【当前时间】以下是各时区此刻的时间，回答任何日期/时间相关问题都必须以此为准："
    ]
    for name in settings.app_timezone_list:
        try:
            tz = ZoneInfo(name)
        except Exception:  # noqa: BLE001 - 无 tzdata 或名称非法时跳过该时区
            continue
        now = datetime.now(tz)
        weekday = "一二三四五六日"[now.weekday()]
        offset = now.strftime("%z")
        label = _TZ_LABELS.get(name, name)
        lines.append(
            f"- {label}（{name}，UTC{offset[:3]}:{offset[3:]}）："
            f"{now.strftime('%Y-%m-%d')} 星期{weekday} {now.strftime('%H:%M')}"
        )
    if len(lines) == 1:
        # 兜底：拿不到任何时区数据时退回系统本地时区
        now = datetime.now().astimezone()
        weekday = "一二三四五六日"[now.weekday()]
        lines.append(
            f"- 本地时间：{now.strftime('%Y-%m-%d')} 星期{weekday} {now.strftime('%H:%M')}"
        )
    lines.append(
        "表中未列出的城市，按其 UTC 偏移换算即可，并在回答中说明是按偏移推算；"
        "不要要求用户自行查询或换算。"
    )
    return "\n".join(lines)


def _make_knowledge_search_tool(company_id: str, sources_bag: list[dict]):
    """构造绑定了企业上下文的 knowledge_search 工具。

    sources_bag：闭包共享列表，收集本次请求实际命中的来源文档，
    供响应结束后向前端返回引用来源。
    """

    @tool
    def knowledge_search(query: str) -> str:
        """检索企业知识库。当问题涉及公司制度、规范、产品资料、项目资料等企业内部信息时，调用此工具获取相关资料。"""

        results = rag_service.search(company_id, query, k=4)
        if not results:
            return (
                "当前企业知识库中未检索到足够信息。请如实告知用户，"
                "并建议在 Knowledge 模块上传相关文档后重试；不要编造答案。"
            )

        formatted: list[str] = []
        for i, (text, meta) in enumerate(results, start=1):
            source_name = meta.get("source", "未知文档")
            score = meta.get("score", 0.0)
            formatted.append(
                f"[{i}] 来源：{source_name}（相关度 {score:.0%}）\n{text}"
            )
            sources_bag.append(
                {
                    "document_id": meta.get("document_id"),
                    "name": source_name,
                    "score": round(score, 3),
                }
            )
        return "【企业知识检索结果】\n\n" + "\n\n".join(formatted)

    return knowledge_search


def _build_messages(
    company_name: str,
    profile: dict,
    history: list[dict],
    question: str,
) -> list:
    system = SystemMessage(
        content=SYSTEM_PROMPT_TEMPLATE.format(
            company_name=company_name,
            user_name=profile.get("name", "员工"),
            department=profile.get("department", "未分配部门"),
            position_part=f"·{profile['position']}" if profile.get("position") else "",
        )
        + "\n\n"
        + now_line()
    )
    messages = [system]
    for m in history:
        if m.get("role") == "user":
            messages.append(HumanMessage(content=m["content"]))
        elif m.get("role") == "assistant":
            messages.append(AIMessage(content=m["content"]))
    messages.append(HumanMessage(content=question))
    return messages


def _dedup_sources(sources_bag: list[dict]) -> list[dict]:
    seen: set = set()
    deduped: list[dict] = []
    for s in sources_bag:
        key = s.get("document_id") or s.get("name")
        if key and key not in seen:
            seen.add(key)
            deduped.append(s)
    return deduped


async def _fallback_rag(
    company_id: str,
    question: str,
    sources_bag: list[dict],
    history: list[dict] | None = None,
    document_ids: list[str] | None = None,
    system_prompt: str | None = None,
    allow_empty_context: bool = False,
):
    """直接 RAG 链：检索 → 流式生成（小模型/Agent 降级路径）。

    document_ids：限定检索范围（Room 关联文档）；
    system_prompt：替换默认系统提示（Room 场景注入项目上下文）；
    allow_empty_context：检索为空时仍生成（Room 场景依据 Timeline 事件作答）。
    """
    model = get_chat_model()
    results = rag_service.search(company_id, question, k=4, document_ids=document_ids)

    if results or allow_empty_context:
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
        else:
            context = "（知识库中未检索到相关资料，请依据系统提示中的项目上下文回答）"

        messages: list = [
            SystemMessage(
                content=f"{system_prompt or RAG_SYSTEM_PROMPT}\n\n{now_line()}"
            )
        ]
        for m in (history or []):
            if m.get("role") == "user":
                messages.append(HumanMessage(content=m["content"]))
            elif m.get("role") == "assistant":
                messages.append(AIMessage(content=m["content"]))
        messages.append(
            HumanMessage(
                content=FALLBACK_PROMPT_TEMPLATE.format(
                    context=context, question=question
                )
            )
        )

        async for chunk in model.astream(messages):
            text = chunk.content if isinstance(chunk.content, str) else ""
            if isinstance(chunk.content, list):
                text = "".join(
                    b.get("text", "") for b in chunk.content if isinstance(b, dict)
                )
            if text:
                yield _sse({"type": "token", "content": text})
    else:
        yield _sse(
            {
                "type": "token",
                "content": "当前企业知识库中未检索到足够信息。你可以在 Knowledge 模块上传企业文档，我将基于它们为你解答。",
            }
        )
    yield _sse({"type": "sources", "sources": _dedup_sources(sources_bag)})
    yield _sse({"type": "done"})


# ---------- Room（项目房间）对话：注入项目上下文 ----------


def _format_room_context_block(room_context: dict) -> str:
    """把 room_service.build_room_context 的结果格式化为提示词块。"""
    lines = [
        "【项目信息】",
        f"名称：{room_context.get('name', '未知项目')}",
        f"状态：{room_context.get('status', '未知')}",
        f"简介：{room_context.get('description') or '暂无'}",
        "",
        "【项目成员】",
        *(room_context.get("members") or ["暂无成员"]),
        "",
        "【关联文档】",
        *(room_context.get("documents") or ["暂无关联文档"]),
        "",
        "【最近工作事件（Timeline，时间正序）】",
        *(room_context.get("recent_events") or ["暂无事件记录"]),
    ]
    return "\n".join(lines)


ROOM_RAG_SYSTEM_PROMPT = """你是项目房间内的 AI 工作助手，回答基于以下两类依据：
1. 上方提供的项目上下文（成员/关联文档/最近工作事件）；
2. 用户消息中附带的企业知识库检索资料。

要求：
- 回答项目相关问题（如「最近项目发生了什么」「上次会议决定了什么」「客户关注什么」「有哪些风险」）时，优先依据工作事件 Timeline 归纳，并注明时间；
- 资料中没有的信息如实说明，不要编造；
- 使用简体中文，简洁、专业、条理清晰，适当使用列表。"""


async def stream_room_answer(
    company_id: str,
    room_context: dict,
    history: list[dict],
    question: str,
) -> AsyncGenerator[str, None]:
    """Room AI 对话入口：自动携带项目上下文（SSE 事件流，协议同 assistant chat）。

    检索范围：优先 Room 关联文档；未关联文档时回退全企业知识库。
    """
    context_block = _format_room_context_block(room_context)
    system_prompt = f"{context_block}\n\n{ROOM_RAG_SYSTEM_PROMPT}"

    document_ids = room_context.get("document_ids") or None
    # 未关联文档时回退全企业检索
    if document_ids is not None and len(document_ids) == 0:
        document_ids = None

    yield _sse({"type": "status", "content": "正在检索项目上下文与知识库…"})
    sources: list[dict] = []
    async for evt in _fallback_rag(
        company_id,
        question,
        sources,
        history=history,
        document_ids=document_ids,
        system_prompt=system_prompt,
        allow_empty_context=True,
    ):
        yield evt


async def stream_agent_answer(
    company_id: str,
    company_name: str,
    profile: dict,
    history: list[dict],
    question: str,
    thread_id: str | None = None,
    model_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Knowledge Agent 主入口：SSE 事件流。

    事件类型：status（阶段提示）/ token（回答增量）/ sources（引用来源）
            / done（结束）/ error（错误）。

    编排策略（AGENT_MODE）：
    - always：完整 LangGraph ReAct Agent（要求模型支持 tool-calling）
    - never：直接 RAG 链（检索 → 生成）
    - auto：本地 Ollama 小模型（≤2B）用 RAG 链，其余走 Agent
      —— 小模型 tool-calling 不可靠，会跳过检索直接幻觉作答。
    """
    mode = settings.AGENT_MODE
    if mode == "never":
        use_agent = False
    elif mode == "always":
        use_agent = True
    else:  # auto
        use_agent = supports_tool_calling()

    if not use_agent:
        yield _sse({"type": "status", "content": "正在检索企业知识库…"})
        sources: list[dict] = []
        async for evt in _fallback_rag(
            company_id, question, sources, history=history
        ):
            yield evt
        return

    sources_bag: list[dict] = []
    knowledge_search = _make_knowledge_search_tool(company_id, sources_bag)
    model = get_chat_model(model_id)
    agent = create_react_agent(
        model=model, tools=[knowledge_search], checkpointer=_checkpointer
    )
    messages = _build_messages(company_name, profile, history, question)
    # 服务端记忆（MemorySaver）：thread_id 存在时信任 Checkpointer 状态，避免历史重复注入
    if thread_id:
        messages = [messages[0], messages[-1]]

    config: dict = {"recursion_limit": 30}
    if thread_id:
        config["configurable"] = {"thread_id": thread_id}

    emitted = False
    tool_called = False
    streamed_text = ""
    try:
        async for event in agent.astream_events(
            {"messages": messages}, version="v2", config=config
        ):
            if event["event"] == "on_tool_start" and event["name"] == "knowledge_search":
                tool_called = True
                yield _sse({"type": "status", "content": "正在检索企业知识库…"})
            elif event["event"] == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk is None:
                    continue
                content = chunk.content
                text = ""
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = "".join(
                        b.get("text", "")
                        for b in content
                        if isinstance(b, dict)
                    )
                if text:
                    emitted = True
                    streamed_text += text
                    yield _sse({"type": "token", "content": text})
    except Exception:  # noqa: BLE001
        logger.exception("Knowledge Agent 执行异常，降级为直接 RAG")
        if not emitted:
            async for evt in _fallback_rag(
                company_id, question, sources_bag, history=history
            ):
                yield evt
            return
        yield _sse({"type": "error", "message": "回答生成中断，请重试"})
        yield _sse({"type": "done"})
        return

    # RAG 对话断链修复（T04.8）：Agent 结束但全程未调用工具，且已流出的文本
    # 是"承诺去查"的过渡话术（如"请稍等，我将为您查询"）→ 立即降级为确定性
    # RAG（检索 → 生成），保证用户拿到最终答案与来源引用，而不是对话中断。
    if not tool_called and re.search(
        r"(请稍等|稍等片刻|正在查询|正在检索|查询中|为您查询|马上(查询|检索)|让我(查询|查一下|检索)|(我|我来|帮你)(查询|查一下|检索))",
        streamed_text,
    ):
        yield _sse({"type": "status", "content": "正在检索企业知识库…"})
        async for evt in _fallback_rag(
            company_id, question, sources_bag, history=history
        ):
            yield evt
        return

    # 小模型偶发不输出内容（如空回复）→ 降级
    if not emitted:
        async for evt in _fallback_rag(
            company_id, question, sources_bag, history=history
        ):
            yield evt
        return

    yield _sse({"type": "sources", "sources": _dedup_sources(sources_bag)})
    yield _sse({"type": "done"})
