"""认证 API：注册 / 登录 / 当前用户。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, is_company_admin
from app.core.database import get_db
from app.core.security import create_access_token
from app.models import User
from app.schemas.auth import (
    CompanyMembership,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Annotated[Session, Depends(get_db)]):
    if auth_service.get_user_by_email(db, data.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")
    user = auth_service.register_user(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    user = auth_service.authenticate(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误"
        )
    token = create_access_token(user.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    memberships = auth_service.get_user_memberships(db, current_user.id)
    companies = [
        CompanyMembership(
            id=company.id,
            name=company.name,
            industry=company.industry,
            logo=company.logo,
            employee_id=employee.id,
            department_id=employee.department_id,
            department_name=employee.department.name if employee.department else None,
            position=employee.position,
            status=employee.status,
            is_company_admin=is_company_admin(db, company, current_user),
        )
        for company, employee in memberships
    ]
    return MeResponse(user=UserOut.model_validate(current_user), companies=companies)
