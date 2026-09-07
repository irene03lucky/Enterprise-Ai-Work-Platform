"""Department CRUD（树状结构）。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate


def get_department(db: Session, department_id: str) -> Department | None:
    return db.get(Department, department_id)


def list_departments(db: Session, company_id: str) -> list[Department]:
    return list(
        db.scalars(
            select(Department)
            .where(Department.company_id == company_id)
            .order_by(Department.created_at)
        ).all()
    )


def _ensure_parent_valid(
    db: Session, company_id: str, parent_id: str | None, moved_id: str | None = None
) -> None:
    """父部门必须存在且属于同一企业；且不能形成环（父不能是自己或自己的子孙）。"""
    if parent_id is None:
        return
    parent = db.get(Department, parent_id)
    if parent is None or parent.company_id != company_id:
        raise ValueError("父部门不存在或不属于该企业")
    if moved_id is not None:
        node: Department | None = parent
        while node is not None:
            if node.id == moved_id:
                raise ValueError("不能将部门移动到自身或其子部门下")
            node = node.parent


def create_department(db: Session, company: Company, data: DepartmentCreate) -> Department:
    _ensure_parent_valid(db, company.id, data.parent_id)
    department = Department(company_id=company.id, **data.model_dump())
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def update_department(db: Session, department: Department, data: DepartmentUpdate) -> Department:
    updates = data.model_dump(exclude_unset=True)
    new_parent_id = updates.get("parent_id")
    if new_parent_id is not None and new_parent_id != department.parent_id:
        _ensure_parent_valid(
            db, department.company_id, new_parent_id, moved_id=department.id
        )
    for field, value in updates.items():
        setattr(department, field, value)
    db.commit()
    db.refresh(department)
    return department


def delete_department(db: Session, department: Department) -> None:
    db.delete(department)
    db.commit()
