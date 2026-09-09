"""AI 工作台 API：聚合视图、真人状态、AI 分身与代理权限、AI 代处理事项、AI 分身对话。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_company_with_access, get_current_user
from app.core.database import get_db
from app.models import Company, Employee, User
from app.schemas.workbench import (
    AIActivityResolve,
    AITwinUpdate,
    HumanStatusUpdate,
    WorkbenchChatRequest,
    WorkbenchOut,
)
from app.services import ai_twin_service, workbench_service

router = APIRouter(prefix="/companies/{company_id}/workbench", tags=["workbench"])
items_router = APIRouter(prefix="/companies/{company_id}/ai-items", tags=["workbench"])


def _employee_of(db: Session, company: Company, user: User) -> Employee | None:
    return workbench_service.get_employee(db, company.id, user.id)


@router.get("", response_model=WorkbenchOut)
def get_workbench(
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """工作台聚合：真人状态 + AI 分身 / AI 代处理事项 / 今日日程 / 项目 Update / 任务概览。"""
    employee = _employee_of(db, company, current_user)
    return workbench_service.build_workbench(db, company, current_user, employee)


@router.patch("/human-status", response_model=WorkbenchOut)
def update_human_status(
    data: HumanStatusUpdate,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """切换真人状态：在线 / 会议中 / 客户拜访 / 出差 / 请假 / 离线。"""
    employee = _employee_of(db, company, current_user)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前用户不是该企业员工")
    employee.status = data.status
    db.commit()
    db.refresh(employee)
    return workbench_service.build_workbench(db, company, current_user, employee)


@router.patch("/ai-twin", response_model=WorkbenchOut)
def update_ai_twin(
    data: AITwinUpdate,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """配置 AI 数字分身：名称 / 状态（关闭·仅辅助·开启代理）/ 代理权限勾选。"""
    employee = _employee_of(db, company, current_user)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前用户不是该企业员工")

    if data.ai_twin_name is not None:
        employee.ai_twin_name = data.ai_twin_name
    if data.ai_twin_status is not None:
        employee.ai_twin_status = data.ai_twin_status
    if data.ai_permissions is not None:
        merged = employee.effective_permissions()
        for key, value in data.ai_permissions.items():
            if key in merged:
                merged[key] = bool(value)
        employee.ai_permissions = merged
    db.commit()
    db.refresh(employee)
    return workbench_service.build_workbench(db, company, current_user, employee)


@router.post("/chat")
async def workbench_chat(
    data: WorkbenchChatRequest,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """AI 分身对话（SSE）。

    事件：status / intent（QUERY|ACTION|FOLLOW_UP|AMBIGUOUS）/ token / sources
    / task_created（已按授权自动创建）/ ai_items / conversation / done / error。
    """
    employee = _employee_of(db, company, current_user)
    from app.ai import model_registry

    generator = ai_twin_service.stream_workbench_answer(
        db=db,
        company=company,
        user=current_user,
        employee=employee,
        history=[m.model_dump() for m in data.history],
        question=data.message,
        conversation_id=data.conversation_id,
        room_id=data.room_id,
        model_id=model_registry.resolve_enabled(data.model_id),
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


@items_router.get("", response_model=list)
def list_ai_items(
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
):
    """AI 已回复 / 已接收 / 新生成 Task / 待本人确认 的事项列表。"""
    employee = _employee_of(db, company, current_user)
    if employee is None:
        return []
    return workbench_service.list_ai_items(db, company.id, employee.id, limit=limit)


@items_router.patch("/{activity_id}")
def resolve_ai_item(
    activity_id: str,
    data: AIActivityResolve,
    company: Annotated[Company, Depends(get_company_with_access)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """处理「待本人确认事项」（确认或重新打开）。"""
    employee = _employee_of(db, company, current_user)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前用户不是该企业员工")
    activity = workbench_service.resolve_activity(
        db, activity_id, employee.id, resolved=data.resolved
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="事项不存在")
    return {"id": activity.id, "resolved": activity.resolved}
