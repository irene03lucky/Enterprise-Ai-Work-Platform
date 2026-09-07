"""Organization API：企业组织树。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_company_with_access
from app.core.database import get_db
from app.models import Company
from app.schemas.organization import OrganizationTreeResponse
from app.services import organization_service

router = APIRouter(prefix="/companies/{company_id}/organization", tags=["organization"])


@router.get("/tree", response_model=OrganizationTreeResponse)
def get_organization_tree(
    company: Annotated[Company, Depends(get_company_with_access)],
    db: Annotated[Session, Depends(get_db)],
):
    tree = organization_service.build_organization_tree(db, company)
    return OrganizationTreeResponse(company=tree)
