"""Role API（基础角色管理，非 RBAC）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_company_with_access
from app.core.database import get_db
from app.models import Company
from app.schemas.role import RoleAssign, RoleCreate, RoleOut, UserRoleOut
from app.services import role_service

router = APIRouter(prefix="/companies/{company_id}/roles", tags=["roles"])


@router.get("", response_model=list[RoleOut])
def list_roles(
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    return role_service.list_roles(db, company.id)


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    data: RoleCreate,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    return role_service.create_role(db, company, data)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    from sqlalchemy import select

    from app.models import Role

    role = db.scalar(select(Role).where(Role.id == role_id, Role.company_id == company.id))
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    role_service.delete_role(db, role)


@router.post("/assign", response_model=UserRoleOut)
def assign_role(
    data: RoleAssign,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return role_service.assign_role(db, data.user_id, data.role_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/users/{user_id}", response_model=list[UserRoleOut])
def list_user_roles(
    user_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    return role_service.list_user_roles(db, user_id)
