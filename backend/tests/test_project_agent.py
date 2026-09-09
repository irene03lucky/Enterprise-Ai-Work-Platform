"""Project Agent 测试：意图识别、任务抽取规则、端到端对话闭环。"""

import json
from datetime import date, timedelta

import pytest

from app.services.project_agent_service import (
    INTENT_ACTION,
    INTENT_FOLLOW_UP,
    INTENT_QUERY,
    _heuristic_proposal,
    _parse_due_date,
    classify_intent,
    detect_and_extract,
)
from tests.test_knowledge import _ollama_ready
from tests.test_room import _create_company, _create_room

AI_MODELS = ("bge-m3", "qwen2.5:1.5b")


# ---------- 意图识别（纯规则，不依赖模型） ----------


@pytest.mark.parametrize(
    "question",
    [
        "项目现在怎么样？",
        "最近项目有什么变化？",
        "当前有哪些风险？",
        "还有哪些待处理事项？",
        "上次会议决定了什么？",
        "客户目前最关注什么？",
    ],
)
def test_query_intent_does_not_create_task(question):
    assert classify_intent(question) == INTENT_QUERY


@pytest.mark.parametrize(
    "question",
    [
        "让李四周五前完成测试",
        "请张三天前整理客户反馈",
        "安排王五本周五前提交报价",
        "@赵六 记得更新项目文档",
    ],
)
def test_action_intent(question):
    assert classify_intent(question) == INTENT_ACTION


@pytest.mark.parametrize(
    "question",
    ["上线以后告诉我", "有进展提醒我", "上线以后记得跟进一下客户反馈"],
)
def test_follow_up_intent(question):
    assert classify_intent(question) == INTENT_FOLLOW_UP


def test_due_date_parsing():
    today = date.today()
    assert _parse_due_date("今天完成") == today
    assert _parse_due_date("明天提交") == today + timedelta(days=1)
    assert _parse_due_date("后天交付") == today + timedelta(days=2)
    assert _parse_due_date("2026-09-11 之前") == date(2026, 9, 11)
    assert _parse_due_date("9月11日前完成") in (date(2026, 9, 11), date(2027, 9, 11))

    # 周X：解析结果应为未来的那一天，且星期匹配
    monday_next_week = _parse_due_date("下周一完成")
    assert monday_next_week.weekday() == 0
    assert monday_next_week > today


def test_heuristic_proposal_extracts_assignee_and_due():
    ctx = {"member_names": []}
    proposal = _heuristic_proposal("让李四周五前完成测试", INTENT_ACTION, ctx)
    assert proposal.assignee_name == "李四"
    assert proposal.due_date is not None
    assert proposal.due_date.weekday() == 4  # 周五
    assert proposal.source_quote == "让李四周五前完成测试"
    assert "测试" in proposal.title

    # 跟进事项标题带前缀
    proposal = _heuristic_proposal("上线以后告诉我", INTENT_FOLLOW_UP, ctx)
    assert proposal.title.startswith("跟进")
    assert proposal.source == "FOLLOW_UP"


def test_heuristic_proposal_prefers_member_name():
    ctx = {"member_names": ["张三", "平台管理员"]}
    proposal = _heuristic_proposal("请张三明天提交报价", INTENT_ACTION, ctx)
    assert proposal.assignee_name == "张三"


@pytest.mark.anyio
async def test_detect_and_extract_query_has_no_proposal():
    intent, proposals = await detect_and_extract("项目现在怎么样？", {"member_names": []})
    assert intent == INTENT_QUERY
    assert proposals == []


@pytest.mark.anyio
async def test_detect_and_extract_action():
    intent, proposals = await detect_and_extract(
        "让李四周五前完成测试", {"member_names": []}
    )
    assert intent == INTENT_ACTION
    assert len(proposals) >= 1
    assert proposals[0].title


# ---------- 端到端（需要 Ollama） ----------


@pytest.mark.skipif(
    not _ollama_ready(AI_MODELS),
    reason="Ollama 或所需模型不可用",
)
def test_project_agent_query_summarizes_project(client, auth_headers):
    """验收①：项目状态总结能引用工作事件中的关键信息。"""
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id, "品牌官网升级项目")
    client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/events",
        json={"type": "customer_feedback", "content": "客户希望增加数字人导览，预算控制在50万元以内。"},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/events",
        json={"type": "meeting", "content": "项目启动会：确认官网升级范围，目标下季度上线。"},
        headers=auth_headers,
    )

    with client.stream(
        "POST",
        f"/api/v1/companies/{company_id}/rooms/{room_id}/chat",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"message": "当前项目情况如何？客户有什么要求？", "history": []},
    ) as resp:
        assert resp.status_code == 200
        intents, tokens = [], []
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] == "token":
                tokens.append(event["content"])
            elif event["type"] == "intent":
                intents.append(event["intent"])
        answer = "".join(tokens)
        assert intents == ["QUERY"], intents
        assert "50万" in answer or "50 万" in answer, answer


@pytest.mark.skipif(
    not _ollama_ready(AI_MODELS),
    reason="Ollama 或所需模型不可用",
)
def test_project_agent_proposes_task_without_creating(client, auth_headers):
    """验收②：明确行动要求 → 返回任务提案且**不自动创建**任务。"""
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)

    with client.stream(
        "POST",
        f"/api/v1/companies/{company_id}/rooms/{room_id}/chat",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"message": "让李四周五前完成测试", "history": []},
    ) as resp:
        assert resp.status_code == 200
        intents, proposals = [], []
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] == "intent":
                intents.append(event["intent"])
            elif event["type"] == "task_proposals":
                proposals = event["proposals"]
        assert intents == ["ACTION"], intents
        assert proposals, "应返回任务提案"
        assert proposals[0]["title"]

    # AI 只提案，未经确认不落库
    tasks = client.get(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks", headers=auth_headers
    ).json()
    assert tasks == []

    # 用户确认后创建
    created = client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks/from-proposal",
        json={"proposals": proposals},
        headers=auth_headers,
    ).json()
    assert len(created) == 1
    assert created[0]["source"] == "CHAT"
    assert "测试" in created[0]["title"]
