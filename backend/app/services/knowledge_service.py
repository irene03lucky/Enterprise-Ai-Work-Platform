"""Knowledge 服务层：知识空间与文档资产管理。"""

import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.vectorstore import delete_company_vectors
from app.core.config import settings
from app.models import Company, DocumentStatus, KnowledgeDocument, KnowledgeSpace
from app.schemas.knowledge import KnowledgeSpaceCreate, KnowledgeSpaceUpdate
from app.services import rag_service
from app.services.document_parser import SUPPORTED_EXTENSIONS


def list_spaces(db: Session, company_id: str) -> list[tuple[KnowledgeSpace, int]]:
    """返回 (空间, 文档数) 列表。"""
    spaces = list(
        db.scalars(
            select(KnowledgeSpace)
            .where(KnowledgeSpace.company_id == company_id)
            .order_by(KnowledgeSpace.created_at)
        ).all()
    )
    if not spaces:
        return []
    counts = dict(
        db.execute(
            select(
                KnowledgeDocument.knowledge_space_id,
                func.count(KnowledgeDocument.id),
            )
            .where(
                KnowledgeDocument.company_id == company_id,
                KnowledgeDocument.knowledge_space_id.in_([s.id for s in spaces]),
            )
            .group_by(KnowledgeDocument.knowledge_space_id)
        ).all()
    )
    return [(space, counts.get(space.id, 0)) for space in spaces]


def get_space(db: Session, company_id: str, space_id: str) -> KnowledgeSpace | None:
    space = db.get(KnowledgeSpace, space_id)
    if space is None or space.company_id != company_id:
        return None
    return space


def create_space(
    db: Session, company: Company, data: KnowledgeSpaceCreate, owner_id: str | None = None
) -> KnowledgeSpace:
    space = KnowledgeSpace(
        company_id=company.id,
        name=data.name,
        description=data.description,
        visibility=data.visibility,
        owner_id=owner_id,
    )
    db.add(space)
    db.commit()
    db.refresh(space)
    return space


def update_space(db: Session, space: KnowledgeSpace, data: KnowledgeSpaceUpdate) -> KnowledgeSpace:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(space, field, value)
    db.commit()
    db.refresh(space)
    return space


def delete_space(db: Session, space: KnowledgeSpace) -> None:
    """删除空间：数据库级联删文档，向量逐一清理，物理文件清理。"""
    documents = list(
        db.scalars(
            select(KnowledgeDocument).where(KnowledgeDocument.knowledge_space_id == space.id)
        ).all()
    )
    for doc in documents:
        rag_service.delete_document_vectors(doc.company_id, doc.id)
        _remove_file(doc.storage_path)
    db.delete(space)
    db.commit()


def list_documents(db: Session, space_id: str) -> list[KnowledgeDocument]:
    return list(
        db.scalars(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.knowledge_space_id == space_id)
            .order_by(KnowledgeDocument.created_at.desc())
        ).all()
    )


def get_document(db: Session, company_id: str, document_id: str) -> KnowledgeDocument | None:
    doc = db.get(KnowledgeDocument, document_id)
    if doc is None or doc.company_id != company_id:
        return None
    return doc


def save_uploaded_file(
    db: Session,
    space: KnowledgeSpace,
    filename: str,
    content: bytes,
    uploader_id: str | None,
) -> tuple[KnowledgeDocument, str | None]:
    """保存上传文件并创建文档资产记录。

    返回 (文档记录, 错误信息)。错误信息非空时（扩展名/大小不合法）
    不落库。
    """
    ext = Path(filename or "").suffix.lower().lstrip(".")
    if ext not in SUPPORTED_EXTENSIONS:
        return None, f"不支持的文件类型 .{ext}（支持 PDF/DOCX/PPTX/TXT/MD）"

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        return None, f"文件超过大小限制（{settings.MAX_UPLOAD_MB}MB）"

    document_id = str(uuid.uuid4())
    file_dir = Path(settings.UPLOAD_DIR) / space.company_id
    file_dir.mkdir(parents=True, exist_ok=True)
    storage_path = file_dir / f"{document_id}.{ext}"
    storage_path.write_bytes(content)

    doc = KnowledgeDocument(
        id=document_id,
        knowledge_space_id=space.id,
        company_id=space.company_id,
        name=(filename or "未命名")[:300],
        file_type=ext,
        file_size=len(content),
        storage_path=str(storage_path),
        status=DocumentStatus.UPLOADED,
        uploader_id=uploader_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc, None


def delete_document(db: Session, doc: KnowledgeDocument) -> None:
    rag_service.delete_document_vectors(doc.company_id, doc.id)
    _remove_file(doc.storage_path)
    db.delete(doc)
    db.commit()


def delete_company_knowledge(db: Session, company_id: str) -> None:
    """企业删除时清理其全部知识资产（由 companies API 调用）。"""
    delete_company_vectors(company_id)
    docs = list(
        db.scalars(
            select(KnowledgeDocument).where(KnowledgeDocument.company_id == company_id)
        ).all()
    )
    for doc in docs:
        _remove_file(doc.storage_path)
    # 数据库记录由外键级联删除


def _remove_file(storage_path: str | None) -> None:
    if not storage_path:
        return
    try:
        Path(storage_path).unlink(missing_ok=True)
    except OSError:
        pass
