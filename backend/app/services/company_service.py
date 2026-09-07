"""Company CRUD。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company
from app.schemas.company import CompanyCreate, CompanyUpdate


def get_company(db: Session, company_id: str) -> Company | None:
    return db.get(Company, company_id)


def list_companies(db: Session) -> list[Company]:
    return list(db.scalars(select(Company).order_by(Company.created_at)).all())


def create_company(db: Session, data: CompanyCreate, owner_id: str | None = None) -> Company:
    company = Company(**data.model_dump(), owner_id=owner_id)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def update_company(db: Session, company: Company, data: CompanyUpdate) -> Company:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company


def delete_company(db: Session, company: Company) -> None:
    """删除企业：先清理其全部知识资产（向量/文件），再删除企业。"""
    from app.services import knowledge_service

    knowledge_service.delete_company_knowledge(db, company.id)
    db.delete(company)
    db.commit()
