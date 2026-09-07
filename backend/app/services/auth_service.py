"""用户注册 / 登录 / 当前用户。"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password, verify_password
from app.models import Company, Employee, User
from app.schemas.auth import RegisterRequest


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def register_user(db: Session, data: RegisterRequest) -> User:
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def get_user_companies(db: Session, user_id: str) -> list[Company]:
    return list(
        db.scalars(
            select(Company).join(Employee, Employee.company_id == Company.id).where(
                Employee.user_id == user_id
            )
        ).all()
    )


def get_user_memberships(db: Session, user_id: str) -> list[tuple[Company, Employee]]:
    """返回 (企业, 员工档案) 列表，员工档案已预加载部门关系。"""
    stmt = (
        select(Company, Employee)
        .join(Employee, Employee.company_id == Company.id)
        .where(Employee.user_id == user_id)
        .options(selectinload(Employee.department))
        .order_by(Company.created_at, Employee.created_at)
    )
    return list(db.execute(stmt).all())
