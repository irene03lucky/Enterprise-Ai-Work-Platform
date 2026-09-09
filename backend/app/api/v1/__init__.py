from fastapi import APIRouter

from app.api.v1 import (
    auth,
    chat,
    companies,
    conversations,
    departments,
    employees,
    health,
    knowledge,
    models,
    organization,
    roles,
    room_chat,
    rooms,
    schedules,
    tasks,
    workbench,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(models.router)
api_router.include_router(companies.router)
api_router.include_router(departments.router)
api_router.include_router(employees.router)
api_router.include_router(roles.router)
api_router.include_router(organization.router)
api_router.include_router(knowledge.router)
api_router.include_router(chat.router)
api_router.include_router(rooms.router)
api_router.include_router(room_chat.router)
api_router.include_router(tasks.room_router)
api_router.include_router(tasks.router)
api_router.include_router(workbench.router)
api_router.include_router(workbench.items_router)
api_router.include_router(schedules.router)
api_router.include_router(conversations.router)
