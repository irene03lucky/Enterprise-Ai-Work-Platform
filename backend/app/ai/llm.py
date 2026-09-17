"""LLM / Embedding Provider 抽象。

- 生成模型：LLM_PROVIDER 切换（ollama 本地 / openai-compatible 端点如 AutoDL）
- 向量模型：固定走 Ollama（bge-m3）。向量必须与 Chroma 中已入库的
  保持一致，因此不随生成模型切换。
"""

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings


def get_chat_model(model_id: str | None = None) -> BaseChatModel:
    """生成模型：默认 Ollama 本地，可切 AutoDL 等 OpenAI 兼容端点。

    model_id：用户在 Model Registry 中选择的模型（'ollama:qwen2.5:7b' 或裸模型名）；
    传入前应已经 model_registry.resolve_enabled 校验。RAG/Chroma 与此选择完全解耦。
    """
    from app.ai import model_registry

    provider_override, name_override = model_registry.parse_model_id(model_id)
    model_name = name_override or settings.LLM_MODEL
    provider = provider_override or settings.LLM_PROVIDER

    if provider == "openai-compatible":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name,
            base_url=settings.LLM_BASE_URL or None,
            api_key=settings.LLM_API_KEY or "EMPTY",
            temperature=0.1,
            max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        )
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=model_name,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.1,
        # 小模型（3B）在长回答时容易陷入重复循环（如把同一项刷上百遍）：
        # 用重复惩罚 + 输出上限双重约束，避免无限重复。
        repeat_penalty=1.15,
        repeat_last_n=256,
        num_predict=settings.LLM_MAX_OUTPUT_TOKENS,
    )


@lru_cache
def get_embeddings() -> Embeddings:
    """向量模型：固定 Ollama bge-m3，保证与 Chroma 存量向量一致。"""
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(
        model=settings.EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )
