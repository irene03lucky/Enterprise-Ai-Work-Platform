"""Employee API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_company_as_admin,
    get_company_with_access,
    get_current_user,
    is_company_admin,
)
from app.core.database import get_db
from app.models import Company, User
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    EmployeeUserCreate,
)
from app.services import employee_service

router = APIRouter(prefix="/companies/{company_id}/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeOut])
def list_employees(
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    return employee_service.list_employees(db, company.id)


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    data: EmployeeCreate,
    company: Annotated[Company, Depends(get_company_as_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return employee_service.create_employee(db, company, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/with-user", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee_with_user(
    data: EmployeeUserCreate,
    company: Annotated[Company, Depends(get_company_as_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    """一步创建：注册用户并加入企业（管理员建员工场景）。"""
    try:
        return employee_service.create_employee_with_user(db, company, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: str,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    employee = employee_service.get_employee(db, employee_id)
    if employee is None or employee.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="员工不存在")
    _ = employee.user
    return employee


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: str,
    data: EmployeeUpdate,
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    employee = employee_service.get_employee(db, employee_id)
    if employee is None or employee.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="员工不存在")

    # 权限：企业管理员可维护任意成员；普通成员仅可修改**自己的真人状态**
    if not is_company_admin(db, company, current_user):
        if employee.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="只能修改自己的信息"
            )
        changed = set(data.model_dump(exclude_unset=True).keys())
        if changed - {"status"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="普通成员仅可修改自己的工作状态",
            )
    try:
        return employee_service.update_employee(db, employee, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(
    employee_id: str,
    company: Annotated[Company, Depends(get_company_as_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    employee = employee_service.get_employee(db, employee_id)
    if employee is None or employee.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="员工不存在")
    employee_service.delete_employee(db, employee)
