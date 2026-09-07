"""Employee CRUD。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Company, Department, Employee, User
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeUserCreate


def get_employee(db: Session, employee_id: str) -> Employee | None:
    return db.get(Employee, employee_id)


def list_employees(db: Session, company_id: str) -> list[Employee]:
    return list(
        db.scalars(
            select(Employee)
            .where(Employee.company_id == company_id)
            .order_by(Employee.created_at)
        ).all()
    )


def _ensure_department_valid(db: Session, company_id: str, department_id: str | None) -> None:
    if department_id is None:
        return
    department = db.get(Department, department_id)
    if department is None or department.company_id != company_id:
        raise ValueError("部门不存在或不属于该企业")


def _employee_out(employee: Employee) -> Employee:
    """确保 user 关系已加载（供 schema 冗余字段使用）。"""
    _ = employee.user
    return employee


def create_employee(db: Session, company: Company, data: EmployeeCreate) -> Employee:
    _ensure_department_valid(db, company.id, data.department_id)
    user = db.get(User, data.user_id)
    if user is None:
        raise ValueError("用户不存在")
    employee = Employee(company_id=company.id, **data.model_dump())
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return _employee_out(employee)


def create_employee_with_user(
    db: Session, company: Company, data: EmployeeUserCreate
) -> Employee:
    """一步完成：创建用户 + 创建员工记录（验收场景 3：创建员工）。"""
    from app.services.auth_service import get_user_by_email

    _ensure_department_valid(db, company.id, data.department_id)
    user = get_user_by_email(db, data.email)
    if user is not None:
        raise ValueError("该邮箱已被注册")
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.flush()
    employee = Employee(
        user_id=user.id,
        company_id=company.id,
        department_id=data.department_id,
        position=data.position,
        status=data.status,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return _employee_out(employee)


def update_employee(db: Session, employee: Employee, data: EmployeeUpdate) -> Employee:
    updates = data.model_dump(exclude_unset=True)
    new_department_id = updates.get("department_id")
    if new_department_id is not None and new_department_id != employee.department_id:
        _ensure_department_valid(db, employee.company_id, new_department_id)
    for field, value in updates.items():
        setattr(employee, field, value)
    db.commit()
    db.refresh(employee)
    return _employee_out(employee)


def delete_employee(db: Session, employee: Employee) -> None:
    db.delete(employee)
    db.commit()
