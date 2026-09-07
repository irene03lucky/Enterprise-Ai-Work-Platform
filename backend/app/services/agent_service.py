"""Knowledge Agent：LangGraph ReAct Agent + 企业知识检索工具。

用户流程：员工提问 → Agent 判断是否需要检索 → 调用 knowledge_search
Tool → Chroma 检索相关文档 → Ollama 生成回答 → 返回答案 + 来源文档。

Agent 失败时自动降级为直接 RAG 链（检索 → 生成），保证可用性。
"""

import json
import logging
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from app.ai.llm import get_chat_model
from app.core.config import settings
from app.services import rag_service

logger = logging.getLogger(__name__)

# 已验证无法稳定 tool-calling 的本地小模型：跳过 Agent 编排，直接 RAG
_SMALL_MODELS_WITHOUT_TOOL_CALLING = {
    "qwen2.5:0.5b",
    "qwen2.5:1.5b",
    "qwen2.5:1b",
    "llama3.2:1b",
    "llama3.2:3b",
    "qwen2.5:3b",
}

SYSTEM_PROMPT_TEMPLATE = """你是「{company_name}」的企业 AI 工作助手。

当前用户：{user_name}（{department}{position_part}）

你的职责：
1. 当问题涉及公司制度、规范、产品、项目资料等企业内部信息时，必须先调用 knowledge_search 工具检索企业知识库，再基于检索结果回答；
2. 回答企业相关问题时必须以检索到的资料为依据，资料中没有的信息要明确说明"企业知识库中暂无相关资料"；
3. 与企业知识无关的通用问题可以直接回答；
4. 使用简体中文，简洁、专业、条理清晰，适当使用列表。"""

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


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


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
            return "企业知识库为空或暂无相关资料。可以建议用户先在 Knowledge 模块上传文档。"

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

        messages: list = [SystemMessage(content=system_prompt or RAG_SYSTEM_PROMPT)]
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
                "content": "企业知识库中暂无相关资料。你可以在 Knowledge 模块上传企业文档，我将基于它们为你解答。",
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
    if mode == "auto":
        is_small_local = (
            settings.LLM_PROVIDER == "ollama"
            and settings.LLM_MODEL in _SMALL_MODELS_WITHOUT_TOOL_CALLING
        )
        use_agent = not is_small_local
    else:
        use_agent = mode == "always"

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
    model = get_chat_model()
    agent = create_react_agent(model=model, tools=[knowledge_search])
    messages = _build_messages(company_name, profile, history, question)

    emitted = False
    try:
        async for event in agent.astream_events(
            {"messages": messages}, version="v2", config={"recursion_limit": 30}
        ):
            if event["event"] == "on_tool_start" and event["name"] == "knowledge_search":
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

    # 小模型偶发不输出内容（如空回复）→ 降级
    if not emitted:
        async for evt in _fallback_rag(
            company_id, question, sources_bag, history=history
        ):
            yield evt
        return

    yield _sse({"type": "sources", "sources": _dedup_sources(sources_bag)})
    yield _sse({"type": "done"})
