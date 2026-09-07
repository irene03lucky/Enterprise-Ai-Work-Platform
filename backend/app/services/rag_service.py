"""RAG 知识链路：解析 → 分块 → 向量化 → Chroma 存储 / 检索。

流程：文档上传 → Loader 解析 → RecursiveCharacterTextSplitter 分块
     → Ollama(bge-m3) 向量化 → Chroma 存储 → Retriever 检索。
"""

import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ai.vectorstore import get_company_vectorstore
from app.core.database import SessionLocal
from app.models import DocumentStatus, KnowledgeDocument
from app.services.document_parser import parse_file

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
)


def process_document(document_id: str) -> None:
    """后台任务：解析文档 → 分块 → 向量化入库 → 更新状态。

    由 BackgroundTasks 调用（线程池），使用独立数据库会话。
    """
    db = SessionLocal()
    try:
        doc = db.get(KnowledgeDocument, document_id)
        if doc is None:
            return

        doc.status = DocumentStatus.PARSING
        db.commit()

        text = parse_file(doc.storage_path, doc.file_type)
        chunks = _splitter.split_text(text)
        if not chunks:
            raise ValueError("文档内容为空或无法提取文本")

        doc.status = DocumentStatus.EMBEDDING
        db.commit()

        # 重处理前先清理旧向量（幂等）
        delete_document_vectors(doc.company_id, doc.id)

        vectorstore = get_company_vectorstore(doc.company_id)
        metadatas = [
            {
                "document_id": doc.id,
                "space_id": doc.knowledge_space_id,
                "company_id": doc.company_id,
                "source": doc.name,
            }
            for _ in chunks
        ]
        ids = [f"{doc.id}:{i}" for i in range(len(chunks))]
        vectorstore.add_texts(texts=chunks, metadatas=metadatas, ids=ids)

        doc.chunk_count = len(chunks)
        doc.status = DocumentStatus.READY
        doc.error_message = None
        db.commit()
        logger.info("文档向量化完成: %s (%d chunks)", doc.name, len(chunks))
    except Exception as exc:  # noqa: BLE001
        logger.exception("文档处理失败: %s", document_id)
        doc = db.get(KnowledgeDocument, document_id)
        if doc is not None:
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(exc)[:500]
            db.commit()
    finally:
        db.close()


def delete_document_vectors(company_id: str, document_id: str) -> None:
    """删除某文档的全部向量块（按 metadata 精确清理，幂等）。"""
    try:
        vectorstore = get_company_vectorstore(company_id)
        collection = vectorstore._collection  # noqa: SLF001 - 官方 API 未暴露 where 删除
        existing = collection.get(where={"document_id": document_id}, include=[])
        if existing and existing.get("ids"):
            collection.delete(ids=existing["ids"])
    except Exception:  # noqa: BLE001
        logger.warning("清理文档向量失败（可能尚无向量）: %s", document_id, exc_info=True)


def search(
    company_id: str,
    query: str,
    k: int = 4,
    document_ids: list[str] | None = None,
) -> list[tuple[str, dict]]:
    """检索企业知识：返回 (chunk 文本, metadata) 列表，附相关度分数。

    document_ids：限定检索范围到指定文档（如 Room 关联文档）；
    传空列表表示该范围内无文档（返回空），None 表示全企业检索。
    """
    try:
        vectorstore = get_company_vectorstore(company_id)
        if document_ids is not None:
            if len(document_ids) == 0:
                return []
            results = vectorstore.similarity_search_with_score(
                query, k=k, filter={"document_id": {"$in": document_ids}}
            )
        else:
            results = vectorstore.similarity_search_with_score(query, k=k)
    except Exception:  # noqa: BLE001
        logger.exception("知识检索失败: company=%s", company_id)
        return []

    enriched: list[tuple[str, dict]] = []
    for doc, distance in results:
        meta = dict(doc.metadata or {})
        # Chroma 距离越小越相关，转换为 0~1 的相关度
        meta["score"] = max(0.0, min(1.0, 1.0 / (1.0 + float(distance))))
        enriched.append((doc.page_content, meta))
    return enriched
