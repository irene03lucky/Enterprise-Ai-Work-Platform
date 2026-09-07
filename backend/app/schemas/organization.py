"""组织树 Schema：Company -> Department(树) -> Employee。"""

from pydantic import BaseModel

from app.schemas.company import CompanyOut
from app.schemas.department import DepartmentOut
from app.schemas.employee import EmployeeOut


class DepartmentTreeNode(DepartmentOut):
    children: list["DepartmentTreeNode"] = []
    employees: list[EmployeeOut] = []


class CompanyTreeNode(CompanyOut):
    departments: list[DepartmentTreeNode] = []
    unassigned_employees: list[EmployeeOut] = []


class OrganizationTreeResponse(BaseModel):
    company: CompanyTreeNode
