"""Company API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_company_as_admin,
    get_company_with_access,
    get_current_user,
)
from app.core.database import get_db
from app.models import Company, User
from app.schemas.company import CompanyCreate, CompanyOut, CompanyUpdate
from app.services import auth_service, company_service

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyOut])
def list_my_companies(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """当前用户所属的企业空间。"""
    return auth_service.get_user_companies(db, current_user.id)


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(
    data: CompanyCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """创建企业。创建者成为所有者并自动成为员工（拥有自己的企业空间）。"""
    from app.models import Employee

    company = company_service.create_company(db, data, owner_id=current_user.id)
    db.add(Employee(user_id=current_user.id, company_id=company.id, position="管理员"))
    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company: Annotated[Company, Depends(get_company_with_access)]):
    return company


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    data: CompanyUpdate,
    company: Annotated[Company, Depends(get_company_as_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return company_service.update_company(db, company, data)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company: Annotated[Company, Depends(get_company_as_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    company_service.delete_company(db, company)
