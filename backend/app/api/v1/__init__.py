from fastapi import APIRouter

from app.api.v1 import (
    auth,
    chat,
    companies,
    departments,
    employees,
    health,
    knowledge,
    organization,
    roles,
    rooms,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(departments.router)
api_router.include_router(employees.router)
api_router.include_router(roles.router)
api_router.include_router(organization.router)
api_router.include_router(knowledge.router)
api_router.include_router(chat.router)
api_router.include_router(rooms.router)
