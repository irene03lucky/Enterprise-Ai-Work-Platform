"""演示数据种子（幂等）。

用于 Docker 启动后快速体验：
- 管理员 admin@eai.dev / admin123（公司所有者）
- 示例企业 + 三级部门树 + 员工
- 默认知识空间 + 示例文档（差旅制度 / 产品介绍，自动向量化）
"""

import threading
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    Company,
    Department,
    Employee,
    KnowledgeDocument,
    KnowledgeSpace,
    Role,
    Room,
    RoomDocument,
    RoomMember,
    User,
    WorkEvent,
)

ADMIN_EMAIL = "admin@eai.dev"
ADMIN_PASSWORD = "admin123"

DEFAULT_SPACES = [
    ("公司知识", "公司介绍、公告与文化"),
    ("制度规范", "规章制度与流程规范"),
    ("产品业务", "产品资料与业务文档"),
    ("项目资料", "项目文档与交付资料"),
]

SAMPLE_DOCS = [
    {
        "space": "制度规范",
        "filename": "员工差旅管理制度.md",
        "content": """# 员工差旅管理制度

## 差旅标准

### 住宿标准
- 国内出差：一线城市住宿标准为每人每晚 600 元，其他城市为每人每晚 450 元。
- 超出标准需提前申请，经部门负责人与财务负责人双审批后方可报销。

### 交通标准
- 机票：默认经济舱；单程飞行 8 小时以上的长途航班，可申请商务舱。
- 高铁：默认二等座；部门负责人及以上职级可乘坐一等座。
- 市内交通：出差期间实报实销，单日上限 200 元。

### 餐费补贴
- 出差期间每日餐补 150 元，无需提供发票。

## 报销流程

1. 出差结束后 15 个工作日内，在 OA 系统提交差旅报销单。
2. 附上住宿发票、行程单、登机牌等原始凭证。
3. 经部门负责人审批后流转至财务部复核。
4. 财务部复核通过后 10 个工作日内完成打款。

## 其他规定

- 出差 3 天以上（含）须购买旅行意外险，费用公司承担。
- 每次出差前需在系统中提交出差申请，注明事由、目的地与预算。
""",
    },
    {
        "space": "产品业务",
        "filename": "EAI产品介绍.md",
        "content": """# EAI 产品介绍

## 产品定位

EAI（Enterprise AI Work Platform，企业 AI 工作平台）是面向企业内部的 AI 工作层。
目标不是替代飞书、钉钉等办公软件，而是在企业已有办公体系之上，
让 AI 理解企业的组织、知识与项目，辅助员工高效完成工作。

## 核心模块

### AI Assistant（AI 助手）
员工的工作入口。支持自然语言提问，自动检索企业知识库，
基于企业上下文给出可信赖的回答，并支持多轮对话。

### Knowledge（企业知识中心）
将企业内部文档（制度、规范、产品资料、项目文档）转化为
AI 可检索、可理解的知识资产。支持知识空间管理、文档上传、
自动解析与向量化。

### Rooms（工作空间）
围绕项目与话题的协作空间，未来支持团队共享上下文、AI 参与协作。

### Work Center（个人工作中心）
个人任务、日程与工作动态的汇聚地。

## 技术架构

- 前端：Next.js + TypeScript
- 后端：FastAPI + Python
- 数据库：PostgreSQL
- AI：LangChain + LangGraph + Chroma 向量库 + Ollama 本地模型

## 版本规划

- V1：企业模型初始化（组织、部门、员工、角色）
- V2：企业知识库 + RAG + Knowledge Agent
""",
    },
]


def _get_or_create_user(db: Session, name: str, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(name=name, email=email, password_hash=hash_password(password))
        db.add(user)
        db.flush()
    return user


def _create_sample_document(db: Session, space: KnowledgeSpace, doc: dict) -> None:
    """写入示例文档文件并创建文档记录（异步向量化）。"""
    import uuid
    from pathlib import Path

    from app.core.config import settings

    document_id = str(uuid.uuid4())
    file_dir = Path(settings.UPLOAD_DIR) / space.company_id
    file_dir.mkdir(parents=True, exist_ok=True)
    storage_path = file_dir / f"{document_id}.md"
    storage_path.write_text(doc["content"], encoding="utf-8")

    record = KnowledgeDocument(
        id=document_id,
        knowledge_space_id=space.id,
        company_id=space.company_id,
        name=doc["filename"],
        file_type="md",
        file_size=len(doc["content"].encode("utf-8")),
        storage_path=str(storage_path),
        uploader_id=space.owner_id,
    )
    db.add(record)
    db.commit()

    # 后台线程完成解析与向量化（模型未就绪时文档会转为 FAILED，可重试）
    from app.services import rag_service

    threading.Thread(
        target=rag_service.process_document,
        args=(document_id,),
        daemon=True,
    ).start()


def _ensure_default_knowledge(db: Session, company: Company) -> None:
    """幂等补充默认知识空间与示例文档（企业无任何空间时）。"""
    space_count = db.scalar(
        select(func.count(KnowledgeSpace.id)).where(
            KnowledgeSpace.company_id == company.id
        )
    )
    if space_count and space_count > 0:
        return

    spaces: dict[str, KnowledgeSpace] = {}
    for name, description in DEFAULT_SPACES:
        space = KnowledgeSpace(
            company_id=company.id,
            name=name,
            description=description,
            owner_id=company.owner_id,
        )
        db.add(space)
        db.flush()
        spaces[name] = space

    for doc in SAMPLE_DOCS:
        space = spaces.get(doc["space"])
        if space is not None:
            _create_sample_document(db, space, doc)


def _ensure_demo_room(db: Session, company: Company) -> None:
    """幂等补充演示项目房间（成员/关联文档/Work Event Timeline）。"""
    existing = db.scalar(select(Room).where(Room.company_id == company.id))
    if existing is not None:
        return

    room = Room(
        company_id=company.id,
        name="品牌官网升级项目",
        description="公司官网品牌与内容升级，包含视觉改版、数字人导览与内容迁移。",
        status="ACTIVE",
        owner_id=company.owner_id,
    )
    db.add(room)
    db.flush()

    # 成员：管理员 + 张三（市场部）
    employees = list(
        db.scalars(select(Employee).where(Employee.company_id == company.id)).all()
    )
    by_name = {e.user.name if e.user else "": e for e in employees}
    admin_emp = next((e for e in employees if e.user and e.user.email == ADMIN_EMAIL), None)
    zhangsan = by_name.get("张三")

    if admin_emp:
        db.add(RoomMember(room_id=room.id, employee_id=admin_emp.id, role="OWNER"))
    if zhangsan:
        db.add(RoomMember(room_id=room.id, employee_id=zhangsan.id, role="MEMBER"))

    # 关联文档：产品介绍 + 差旅制度（复用知识库既有资产）
    docs = list(
        db.scalars(
            select(KnowledgeDocument).where(
                KnowledgeDocument.company_id == company.id
            )
        ).all()
    )
    for doc in docs:
        db.add(RoomDocument(room_id=room.id, document_id=doc.id, added_by=company.owner_id))

    # Work Events：项目 Timeline
    author_id = (admin_emp or zhangsan).id if (admin_emp or zhangsan) else None
    events = [
        ("meeting", "项目启动会：确认官网升级范围（视觉改版、内容迁移），目标下季度上线。"),
        ("decision", "决策：首页采用新品牌视觉规范，旧内容逐步迁移不一次性下线。"),
        ("customer_feedback", "今天与客户沟通，对方希望增加数字人导览，预算控制在50万元以内。"),
        ("work_log", "完成官网首页改版的低保真设计稿，已同步设计团队评审。"),
        ("task_update", "内容迁移任务完成 60%，预计下周进入联调。"),
    ]
    for etype, content in events:
        db.add(WorkEvent(room_id=room.id, employee_id=author_id, type=etype, content=content))

    db.commit()
    print("[seed] 演示项目房间「品牌官网升级项目」已就绪")


def _ensure_demo_tasks(db: Session, company: Company) -> None:
    """幂等补充演示任务（待办 / 进行中 / 已完成，含 AI 对话来源示例）。"""
    from datetime import date, timedelta

    from app.models import Task, TaskSource, TaskStatus

    room = db.scalar(select(Room).where(Room.company_id == company.id))
    if room is None:
        return
    existing = db.scalar(select(Task).where(Task.room_id == room.id))
    if existing is not None:
        return

    employees = list(
        db.scalars(select(Employee).where(Employee.company_id == company.id)).all()
    )
    by_name = {e.user.name if e.user else "": e for e in employees}
    admin_emp = next((e for e in employees if e.user and e.user.email == ADMIN_EMAIL), None)
    zhangsan = by_name.get("张三")

    today = date.today()
    demos = [
        (
            "整理数字人导览需求清单并给出报价",
            "客户希望增加数字人导览，预算控制在 50 万元以内，需先出需求清单与区间报价。",
            zhangsan,
            today + timedelta(days=5),
            TaskStatus.TODO,
            TaskSource.CHAT,
            "客户希望增加数字人导览，预算控制在50万元以内",
        ),
        (
            "完成官网首页高保真设计稿",
            "基于新品牌视觉规范输出首页高保真稿，评审通过后进入切图。",
            admin_emp,
            today + timedelta(days=2),
            TaskStatus.IN_PROGRESS,
            TaskSource.WORK_EVENT,
            "完成官网首页改版的低保真设计稿，已同步设计团队评审。",
        ),
        (
            "跟进：官网正式上线后同步客户并收集反馈",
            "上线后第一时间告知客户，并收集使用反馈形成跟进事项。",
            admin_emp,
            None,
            TaskStatus.TODO,
            TaskSource.FOLLOW_UP,
            "上线以后告诉我",
        ),
        (
            "输出首页低保真设计稿并组织评审",
            "已完成，评审结论：结构通过，视觉待细化。",
            admin_emp,
            today - timedelta(days=1),
            TaskStatus.DONE,
            TaskSource.MANUAL,
            None,
        ),
    ]
    for title, desc, assignee, due, tstatus, source, quote in demos:
        db.add(
            Task(
                company_id=company.id,
                room_id=room.id,
                title=title,
                description=desc,
                assignee_employee_id=assignee.id if assignee else None,
                due_date=due,
                status=tstatus,
                source=source,
                source_quote=quote,
                created_by=company.owner_id,
                owner_id=company.owner_id,
                completed_at=datetime.utcnow() if tstatus == TaskStatus.DONE else None,
            )
        )
    db.commit()
    print("[seed] 演示任务（待办/进行中/已完成/跟进）已就绪")


def run_seed() -> None:
    db = SessionLocal()
    try:
        company = db.scalar(select(Company).where(Company.name == "示例科技有限公司"))
        if company is not None:
            # 已初始化过企业：仅补充默认知识空间与演示房间（升级幂等）
            _ensure_default_knowledge(db, company)
            _ensure_demo_room(db, company)
            _ensure_demo_tasks(db, company)
            return

        admin = _get_or_create_user(db, "平台管理员", ADMIN_EMAIL, ADMIN_PASSWORD)

        company = Company(
            name="示例科技有限公司",
            description="EAI 演示企业空间",
            industry="互联网",
            owner_id=admin.id,
        )
        db.add(company)
        db.flush()

        # 部门树
        gen_office = Department(company_id=company.id, name="总经办", description="企业治理与管理协调")
        db.add(gen_office)
        db.flush()

        market = Department(company_id=company.id, name="市场部", description="品牌与增长")
        project = Department(company_id=company.id, name="项目部", description="产品交付")
        finance = Department(company_id=company.id, name="财务部", description="资金与预算")
        db.add_all([market, project, finance])
        db.flush()

        brand = Department(
            company_id=company.id, parent_id=market.id, name="品牌组", description="市场部子团队"
        )
        db.add(brand)
        db.flush()

        # 员工
        employees = [
            Employee(
                user_id=admin.id,
                company_id=company.id,
                department_id=gen_office.id,
                position="管理员",
            ),
            Employee(
                user_id=_get_or_create_user(db, "张三", "zhangsan@eai.dev", "demo1234").id,
                company_id=company.id,
                department_id=market.id,
                position="市场总监",
            ),
            Employee(
                user_id=_get_or_create_user(db, "李四", "lisi@eai.dev", "demo1234").id,
                company_id=company.id,
                department_id=brand.id,
                position="品牌经理",
            ),
            Employee(
                user_id=_get_or_create_user(db, "王五", "wangwu@eai.dev", "demo1234").id,
                company_id=company.id,
                department_id=project.id,
                position="项目负责人",
            ),
        ]
        db.add_all(employees)

        # 角色
        db.add_all(
            [
                Role(company_id=company.id, name="管理员", description="企业管理者"),
                Role(company_id=company.id, name="员工", description="普通员工"),
                Role(company_id=company.id, name="项目负责人", description="项目负责角色"),
            ]
        )

        db.commit()
        print(f"[seed] 演示数据已就绪，管理员账号: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")

        # 默认知识空间 + 示例文档（自动向量化）+ 演示项目房间 + 演示任务
        _ensure_default_knowledge(db, company)
        _ensure_demo_room(db, company)
        _ensure_demo_tasks(db, company)
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
