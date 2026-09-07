"""组织树构建：Company -> Department 树 -> 员工。"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Company, Department, Employee
from app.schemas.employee import EmployeeOut
from app.schemas.organization import CompanyTreeNode, DepartmentTreeNode


def build_organization_tree(db: Session, company: Company) -> CompanyTreeNode:
    """一次性取出企业下全部部门与员工，在内存中组装树，避免 N+1。"""
    departments: list[Department] = list(
        db.scalars(
            select(Department)
            .where(Department.company_id == company.id)
            .options(selectinload(Department.employees).selectinload(Employee.user))
            .order_by(Department.created_at)
        )
    )
    all_employees: list[Employee] = list(
        db.scalars(
            select(Employee)
            .where(Employee.company_id == company.id)
            .options(selectinload(Employee.user))
            .order_by(Employee.created_at)
        )
    )

    dept_nodes: dict[str, DepartmentTreeNode] = {
        dept.id: DepartmentTreeNode(
            id=dept.id,
            company_id=dept.company_id,
            parent_id=dept.parent_id,
            name=dept.name,
            description=dept.description,
            created_at=dept.created_at,
        )
        for dept in departments
    }

    roots: list[DepartmentTreeNode] = []
    for dept in departments:
        node = dept_nodes[dept.id]
        if dept.parent_id and dept.parent_id in dept_nodes:
            dept_nodes[dept.parent_id].children.append(node)
        else:
            roots.append(node)

    company_node = CompanyTreeNode(
        id=company.id,
        name=company.name,
        industry=company.industry,
        logo=company.logo,
        description=company.description,
        owner_id=company.owner_id,
        created_at=company.created_at,
        updated_at=company.updated_at,
        departments=roots,
        unassigned_employees=[
            _employee_to_out(emp)
            for emp in all_employees
            if emp.department_id is None or emp.department_id not in dept_nodes
        ],
    )

    for dept in departments:
        node = dept_nodes[dept.id]
        node.employees = [_employee_to_out(emp) for emp in dept.employees]

    return company_node


def _employee_to_out(emp: Employee) -> EmployeeOut:
    return EmployeeOut(
        id=emp.id,
        user_id=emp.user_id,
        company_id=emp.company_id,
        department_id=emp.department_id,
        position=emp.position,
        status=emp.status,
        created_at=emp.created_at,
        updated_at=emp.updated_at,
        user_name=emp.user.name if emp.user else None,
        user_email=emp.user.email if emp.user else None,
        user_avatar=emp.user.avatar if emp.user else None,
    )
