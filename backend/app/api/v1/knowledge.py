"""Knowledge API：知识空间与文档资产管理。"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_company_with_access, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models import Company, User
from app.schemas.knowledge import (
    KnowledgeDocumentOut,
    KnowledgeSpaceCreate,
    KnowledgeSpaceOut,
    KnowledgeSpaceUpdate,
)
from app.services import knowledge_service, rag_service

router = APIRouter(prefix="/companies/{company_id}/knowledge", tags=["knowledge"])


def _space_out(space, document_count: int) -> KnowledgeSpaceOut:
    out = KnowledgeSpaceOut.model_validate(space)
    out.document_count = document_count
    return out


# ---------- 知识空间 ----------


@router.get("/spaces", response_model=list[KnowledgeSpaceOut])
def list_spaces(
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    return [
        _space_out(space, count)
        for space, count in knowledge_service.list_spaces(db, company.id)
    ]


@router.post("/spaces", response_model=KnowledgeSpaceOut, status_code=status.HTTP_201_CREATED)
def create_space(
    data: KnowledgeSpaceCreate,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    space = knowledge_service.create_space(db, company, data, owner_id=current_user.id)
    return _space_out(space, 0)


@router.patch("/spaces/{space_id}", response_model=KnowledgeSpaceOut)
def update_space(
    space_id: str,
    data: KnowledgeSpaceUpdate,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    space = knowledge_service.get_space(db, company.id, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识空间不存在")
    space = knowledge_service.update_space(db, space, data)
    count = knowledge_service.list_spaces(db, company.id)
    document_count = next((c for s, c in count if s.id == space.id), 0)
    return _space_out(space, document_count)


@router.delete("/spaces/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_space(
    space_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    space = knowledge_service.get_space(db, company.id, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识空间不存在")
    knowledge_service.delete_space(db, space)


# ---------- 文档资产 ----------


@router.get("/spaces/{space_id}/documents", response_model=list[KnowledgeDocumentOut])
def list_documents(
    space_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    space = knowledge_service.get_space(db, company.id, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识空间不存在")
    return knowledge_service.list_documents(db, space.id)


@router.post(
    "/spaces/{space_id}/documents",
    response_model=KnowledgeDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    space_id: str,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """上传文档资产：保存 → 后台解析分块向量化 → 状态流转至 READY。"""
    space = knowledge_service.get_space(db, company.id, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识空间不存在")

    if file.filename is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少文件名")
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件超过大小限制（{settings.MAX_UPLOAD_MB}MB）",
        )

    doc, error = knowledge_service.save_uploaded_file(
        db, space, file.filename, content, uploader_id=current_user.id
    )
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    background_tasks.add_task(rag_service.process_document, doc.id)
    return doc


@router.post("/documents/{document_id}/reprocess", response_model=KnowledgeDocumentOut)
def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    """重新处理文档（失败重试）。"""
    doc = knowledge_service.get_document(db, company.id, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    background_tasks.add_task(rag_service.process_document, doc.id)
    return doc


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    doc = knowledge_service.get_document(db, company.id, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    knowledge_service.delete_document(db, doc)
