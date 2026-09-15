"""统一 Model Registry：可用 LLM 的发现 / 列举 / 校验。

设计要点（T04.8）：
- 模型选择只影响「推理与回答」环节；Knowledge / Chroma / knowledge_search
  是独立的知识来源，切换模型不触碰、不切换企业知识库；
- provider=ollama：动态发现本机 Ollama 已安装的全部模型（本地优先）；
- provider=openai-compatible：取配置的单模型；
- 小模型（≤3B）tool-calling 不可靠，capabilities 不含 tools（Agent 会自动降级 RAG）。
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 与 agent_service._SMALL_MODELS_WITHOUT_TOOL_CALLING 同口径
_SMALL_MODELS_WITHOUT_TOOL_CALLING = {
    "qwen2.5:0.5b",
    "qwen2.5:1.5b",
    "qwen2.5:1b",
    "llama3.2:1b",
    "llama3.2:3b",
    "qwen2.5:3b",
}


def _entry(model_name: str, provider: str, current: bool = False) -> dict[str, Any]:
    return {
        # 带provider前缀的稳定 ID，前端选择后原样回传
        "model_id": f"{provider}:{model_name}",
        "display_name": model_name,
        "provider": provider,
        "model_name": model_name,
        "enabled": True,
        "capabilities": ["chat"]
        + ([] if model_name in _SMALL_MODELS_WITHOUT_TOOL_CALLING else ["tools"]),
        "current": current,
    }


def parse_model_id(model_id: str | None) -> tuple[str | None, str | None]:
    """'ollama:qwen2.5:7b' → ('ollama', 'qwen2.5:7b')；无前缀 → (None, model_id)。"""
    if not model_id:
        return None, None
    for prefix in ("ollama:", "openai-compatible:"):
        if model_id.startswith(prefix):
            return prefix[:-1], model_id[len(prefix) :]
    return None, model_id


def list_models() -> list[dict[str, Any]]:
    """列出全部可用模型（Ollama 动态发现 + 配置默认兜底）。"""
    models: list[dict[str, Any]] = []
    default_name = settings.LLM_MODEL

    if settings.LLM_PROVIDER == "ollama":
        try:
            base = settings.OLLAMA_BASE_URL.rstrip("/")
            resp = httpx.get(f"{base}/api/tags", timeout=3.0)
            resp.raise_for_status()
            names = [
                m.get("name") for m in resp.json().get("models", []) if m.get("name")
            ]
            for name in names:
                models.append(_entry(name, "ollama", current=(name == default_name)))
        except Exception:  # noqa: BLE001
            logger.warning("获取 Ollama 模型列表失败，回退为默认模型", exc_info=True)

        if not models:
            models.append(_entry(default_name, "ollama", current=True))
        elif all(m["model_name"] != default_name for m in models):
            # 配置的默认模型未在 /api/tags 中（异常情况），兜底列出
            models.append(_entry(default_name, "ollama", current=True))
    else:
        # 云端 OpenAI 兼容端点：配置的默认模型 + 可选额外模型（逗号分隔），
        # 供前端「当前模型」下拉切换（RAG 知识库与所选模型无关）。
        names = [default_name]
        for extra in settings.LLM_EXTRA_MODELS.split(","):
            extra = extra.strip()
            if extra and extra not in names:
                names.append(extra)
        for name in names:
            models.append(_entry(name, "openai-compatible", current=(name == default_name)))

    return models


def resolve_enabled(model_id: str | None) -> str | None:
    """校验用户选择的 model_id 是否可用；可用返回 model_name，否则返回 None（用默认）。"""
    if not model_id:
        return None
    _, name = parse_model_id(model_id)
    if not name:
        return None
    for m in list_models():
        if m["model_name"] == name and m["enabled"]:
            return name
    return None
