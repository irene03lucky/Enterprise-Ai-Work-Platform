"""Department API（企业内部门，树状结构）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_company_as_admin, get_company_with_access
from app.core.database import get_db
from app.models import Company
from app.schemas.department import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.services import department_service

router = APIRouter(prefix="/companies/{company_id}/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
def list_departments(
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    return department_service.list_departments(db, company.id)


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    data: DepartmentCreate,
    company: Annotated[Company, Depends(get_company_as_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return department_service.create_department(db, company, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{department_id}", response_model=DepartmentOut)
def get_department(
    department_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    department = department_service.get_department(db, department_id)
    if department is None or department.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    return department


@router.patch("/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: str,
    data: DepartmentUpdate,
    company: Annotated[Company, Depends(get_company_as_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    department = department_service.get_department(db, department_id)
    if department is None or department.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    try:
        return department_service.update_department(db, department, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: str,
    company: Annotated[Company, Depends(get_company_as_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    department = department_service.get_department(db, department_id)
    if department is None or department.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    department_service.delete_department(db, department)
