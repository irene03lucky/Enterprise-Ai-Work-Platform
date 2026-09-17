"""API 公共依赖：认证与企业访问控制。"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Company, Employee, Role, User, UserRole
from app.services.auth_service import get_user_by_email

bearer_scheme = HTTPBearer(auto_error=False)

# 企业管理员角色名（种子数据中的「管理员」角色）
ADMIN_ROLE_NAME = "管理员"


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email = payload.get("sub")
    if email is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


def get_company_with_access(
    company_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Company:
    """企业级访问校验：当前用户须为该企业的成员（员工）或所有者。

    未来这里将替换为基于 Role / visibility 的完整权限判断。
    """
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="企业不存在")
    is_member = (
        db.query(Employee.id)
        .filter(Employee.company_id == company.id, Employee.user_id == current_user.id)
        .first()
        is not None
    )
    if not is_member and company.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该企业")
    return company


def is_company_admin(db: Session, company: Company, user: User) -> bool:
    """企业管理员判定：企业所有者，或持有「管理员」角色的成员。"""
    if company.owner_id == user.id:
        return True
    return (
        db.scalar(
            select(Role.id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                Role.company_id == company.id,
                Role.name == ADMIN_ROLE_NAME,
                UserRole.user_id == user.id,
            )
        )
        is not None
    )


def get_company_as_admin(
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Company:
    """组织管理操作专用依赖：非企业管理员一律 403。

    用于部门 / 员工 / 角色 / 企业信息的增删改。普通成员只能查看组织架构，
    以及修改自己的真人状态（走 /workbench/human-status 与 AI 分身设置）。
    """
    if not is_company_admin(db, company, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅企业管理员可执行该操作",
        )
    return company


def get_current_employee(
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Employee | None:
    """当前用户在该企业下的员工档案（所有者可能没有员工档案，故可空）。"""
    return db.scalar(
        select(Employee).where(
            Employee.company_id == company.id, Employee.user_id == current_user.id
        )
    )
