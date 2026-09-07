"""Chroma 向量库管理：按企业隔离 Collection。"""

import threading

import chromadb
from langchain_chroma import Chroma

from app.ai.llm import get_embeddings
from app.core.config import settings

_client: chromadb.api.ClientAPI | None = None
_client_lock = threading.Lock()


def get_chroma_client() -> chromadb.api.ClientAPI:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = chromadb.PersistentClient(
                    path=settings.CHROMA_DIR,
                    settings=chromadb.config.Settings(anonymized_telemetry=False),
                )
    return _client


def company_collection_name(company_id: str) -> str:
    """Chroma 集合名约束 ^[\\w-]{1,100}$，uuid 中的 '-' 合法，直接使用。"""
    return f"company-{company_id}"


def get_company_vectorstore(company_id: str) -> Chroma:
    """返回某企业的向量库句柄（企业间数据隔离）。"""
    return Chroma(
        client=get_chroma_client(),
        collection_name=company_collection_name(company_id),
        embedding_function=get_embeddings(),
    )


def delete_company_vectors(company_id: str) -> None:
    """删除企业全部向量（企业删除时调用，幂等）。"""
    try:
        get_chroma_client().delete_collection(company_collection_name(company_id))
    except Exception:
        pass  # 集合不存在时忽略
