"""AI Assistant Chat API：Knowledge Agent SSE 流式对话。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_company_with_access, get_current_user
from app.core.database import get_db
from app.models import Company, Employee, User
from app.schemas.chat import ChatRequest
from app.services import agent_service, auth_service

router = APIRouter(prefix="/companies/{company_id}/chat", tags=["chat"])


@router.post("")
async def chat(
    data: ChatRequest,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """AI Assistant 对话入口。

    SSE 事件流：status（检索中提示）/ token（回答增量）
    / sources（引用的企业文档）/ done / error。
    """
    # 用户企业身份，注入 Agent 系统提示词
    memberships = auth_service.get_user_memberships(db, current_user.id)
    membership = next(
        (m for m in memberships if m[0].id == company.id), None
    )
    employee: Employee | None = membership[1] if membership else None
    profile = {
        "name": current_user.name,
        "department": employee.department.name if employee and employee.department else "未分配部门",
        "position": employee.position if employee else None,
    }

    history = [m.model_dump() for m in data.history]
    generator = agent_service.stream_agent_answer(
        company_id=company.id,
        company_name=company.name,
        profile=profile,
        history=history,
        question=data.message,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
