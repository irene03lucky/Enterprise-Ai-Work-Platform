"""Role / UserRole 基础 CRUD。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Role, User, UserRole
from app.schemas.role import RoleCreate


def list_roles(db: Session, company_id: str) -> list[Role]:
    return list(
        db.scalars(
            select(Role).where(Role.company_id == company_id).order_by(Role.created_at)
        ).all()
    )


def create_role(db: Session, company: Company, data: RoleCreate) -> Role:
    role = Role(company_id=company.id, **data.model_dump())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role: Role) -> None:
    db.delete(role)
    db.commit()


def assign_role(db: Session, user_id: str, role_id: str) -> UserRole:
    user = db.get(User, user_id)
    role = db.get(Role, role_id)
    if user is None:
        raise ValueError("用户不存在")
    if role is None:
        raise ValueError("角色不存在")
    existing = db.scalar(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )
    if existing is not None:
        return existing
    user_role = UserRole(user_id=user_id, role_id=role_id)
    db.add(user_role)
    db.commit()
    db.refresh(user_role)
    return user_role


def list_user_roles(db: Session, user_id: str) -> list[UserRole]:
    return list(
        db.scalars(select(UserRole).where(UserRole.user_id == user_id)).all()
    )
