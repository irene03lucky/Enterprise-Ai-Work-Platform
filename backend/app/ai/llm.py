"""LLM / Embedding Provider 抽象。

- 生成模型：LLM_PROVIDER 切换（ollama 本地 / openai-compatible 端点如 AutoDL）
- 向量模型：固定走 Ollama（bge-m3）。向量必须与 Chroma 中已入库的
  保持一致，因此不随生成模型切换。
"""

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings


def get_chat_model() -> BaseChatModel:
    """生成模型：默认 Ollama 本地，可切 AutoDL 等 OpenAI 兼容端点。"""
    if settings.LLM_PROVIDER == "openai-compatible":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL or None,
            api_key=settings.LLM_API_KEY or "EMPTY",
            temperature=0.1,
        )
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.LLM_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.1,
    )


@lru_cache
def get_embeddings() -> Embeddings:
    """向量模型：固定 Ollama bge-m3，保证与 Chroma 存量向量一致。"""
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(
        model=settings.EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )
