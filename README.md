# Enterprise AI Work Platform（EAI）

面向企业内部的 AI 工作平台。目标不是替代飞书、钉钉等办公软件，而是在企业已有办公体系之上建立一个 **AI 工作层**，让 AI 理解企业组织、企业知识、企业项目与员工工作过程。

当前版本：**V3 · EAI-T03 Project Room + Work Event 最小闭环**

## 功能概览

### V1（T01）：产品基础框架与企业模型
- 用户体系：注册 / 登录（JWT）/ 当前用户信息
- 企业模型：创建企业（创建者成为所有者与管理员）
- 组织模型：树状部门结构，支持无限层级
- 员工模型：员工加入企业、归属部门、工作状态
- 角色模型：企业内角色与用户-角色关系（基础建模，非 RBAC）
- AI Assistant：身份化欢迎页 + AI 工作入口（T01.1/T01.2）

### V2（T02）：企业知识库 + RAG + Knowledge Agent
- **Knowledge 模块**：知识空间（公司知识/制度规范/产品业务/项目资料/自定义）+ 文档资产管理
- **文档资产**：PDF / DOCX / PPTX / TXT / Markdown 上传 → 解析 → 状态机（上传/解析/向量化/就绪/失败）→ 元数据与分块统计
- **本地 RAG 链路**：RecursiveCharacterTextSplitter 分块 → Ollama(bge-m3) 向量化 → Chroma 向量库（按企业隔离 Collection）→ Retriever 检索
- **Knowledge Agent**：LangGraph ReAct Agent，`@tool knowledge_search` 检索企业知识，支持多轮对话上下文，返回答案 + 来源文档
- **AI Assistant 集成**：SSE 流式对话，检索状态提示、引用来源展示
- **健康检查**：`/health/ai` 探测 Ollama 连通性与模型就绪状态

## 技术栈

| 层 | 技术 |
| --- | --- |
| Frontend | Next.js 14（App Router）+ TypeScript + Tailwind CSS |
| Backend | FastAPI + Python 3.12 |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 |
| 认证 | JWT（PyJWT）+ bcrypt |
| AI 编排 | LangChain + LangGraph（create_react_agent） |
| 向量库 | Chroma（PersistentClient，按企业隔离） |
| 文档解析 | pypdf / python-docx / python-pptx |
| 模型运行时 | Ollama（bge-m3 向量 + qwen2.5 生成），支持 OpenAI 兼容端点（AutoDL 等）切换 |

## 运行架构

```
Mac 宿主机
├── Ollama（原生运行，Metal GPU 加速）
│   ├── bge-m3          # 向量模型
│   └── qwen2.5:1.5b    # 生成模型
└── Docker Desktop
    ├── eai-backend（FastAPI + LangChain/LangGraph Agent）
    ├── eai-frontend（Next.js）
    ├── eai-db（PostgreSQL）
    └── 卷：eai_data（Chroma 向量库 + 上传文件）
         ↑ 容器经 host.docker.internal:11434 访问宿主 Ollama
```

模型可随时切换到 AutoDL 等云端 OpenAI 兼容端点（改 `.env` 即可，零代码改动）。

## 目录结构

```
EAI/
├── docker-compose.yml        # 全栈编排（db / backend / frontend）
├── .env.example              # 统一环境变量模板
├── backend/
│   ├── app/
│   │   ├── api/              # 路由层（deps 依赖注入）
│   │   │   └── v1/           # auth / companies / departments / employees / roles / organization / knowledge / chat / health
│   │   ├── ai/               # AI 层（llm provider / chroma 向量库）
│   │   ├── core/             # 配置、数据库、安全
│   │   ├── models/           # SQLAlchemy 模型（含 KnowledgeSpace/KnowledgeDocument）
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务逻辑层（含 document_parser / rag_service / agent_service）
│   │   ├── main.py           # FastAPI 入口
│   │   └── seed.py           # 演示数据（幂等，含默认知识空间与示例文档）
│   ├── tests/                # pytest（CRUD / 知识库 / Agent 问答端到端）
│   └── Dockerfile
└── frontend/
    ├── app/                  # 页面（login + workspace 五大导航）
    ├── components/           # 通用组件
    ├── features/             # 业务模块（auth / organization / knowledge）
    ├── lib/                  # API 客户端与类型定义
    └── Dockerfile            # 多阶段构建（standalone 产物）
```

## 快速开始（Docker 推荐）

```bash
# 1. 准备环境变量
cp .env.example .env

# 2. 启动全栈
docker compose up -d --build

# 3. 访问
# 前端：http://localhost:3000
# 后端 API 文档：http://localhost:8000/docs
# 健康检查：http://localhost:8000/health
```

首次启动会自动写入演示数据：

| 账号 | 密码 | 说明 |
| --- | --- | --- |
| admin@eai.dev | admin123 | 企业管理员（示例科技有限公司） |
| zhangsan@eai.dev 等 | demo1234 | 演示员工 |

## 本地开发

### 后端

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 需要本地或 Docker 中的 PostgreSQL（docker compose up -d db）
# 设置环境变量或使用 backend/.env
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000，NEXT_PUBLIC_API_URL 默认指向 localhost:8000
```

### 运行测试

```bash
# 后端（需可用 PostgreSQL，测试库默认 localhost:5433/eai_test）
cd backend
TEST_DATABASE_URI=postgresql://eai:eai_dev_password@localhost:5433/eai_test \
  python -m pytest tests/ -v
```

测试覆盖：API 启动、数据库连接、Company/Department/Employee/Role CRUD、组织树、认证与权限边界、知识空间 CRUD、文档上传→解析→向量化管线、Agent 带来源问答、多轮对话上下文。

## API 一览（/api/v1）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /health · /health/db · /health/ai | 健康检查（AI 链路含 Ollama 连通与模型就绪） |
| POST | /auth/register · /auth/login | 注册 / 登录 |
| GET | /auth/me | 当前用户及其企业身份（公司+部门+职位） |
| GET/POST | /companies | 我的企业 / 创建企业 |
| GET/PATCH/DELETE | /companies/{id} | 企业详情 / 更新 / 删除（级联清理知识资产） |
| GET/POST | /companies/{id}/departments | 部门列表 / 新建 |
| GET/PATCH/DELETE | /companies/{id}/departments/{id} | 部门详情 / 更新（支持移动）/ 删除 |
| GET/POST | /companies/{id}/employees | 员工列表 / 新建（已有用户） |
| POST | /companies/{id}/employees/with-user | 一步创建用户并加入企业 |
| GET/PATCH/DELETE | /companies/{id}/employees/{id} | 员工详情 / 更新 / 删除 |
| GET/POST | /companies/{id}/roles | 角色列表 / 新建 |
| POST | /companies/{id}/roles/assign | 为用户授予角色 |
| GET | /companies/{id}/organization/tree | 组织树（企业→部门→员工） |
| GET/POST | /companies/{id}/knowledge/spaces | 知识空间列表 / 创建 |
| PATCH/DELETE | /companies/{id}/knowledge/spaces/{id} | 空间更新 / 删除（清理向量与文件） |
| GET/POST | /companies/{id}/knowledge/spaces/{id}/documents | 文档列表 / 上传（后台解析向量化） |
| POST | /companies/{id}/knowledge/documents/{id}/reprocess | 文档重新处理（失败重试） |
| DELETE | /companies/{id}/knowledge/documents/{id} | 删除文档（含向量） |
| POST | /companies/{id}/chat | AI Assistant 对话（SSE 流式，含来源） |

## 设计说明

- **非 OA**：不包含即时通讯、审批流、考勤、薪资等传统 OA 功能；员工 `status` 是供未来 AI 理解工作状态的信号，不是考勤。
- **权限预留**：本轮只做"企业成员可见性"边界（成员或所有者可访问），完整 RBAC 与 `visibility`（PRIVATE/DEPARTMENT/PROJECT/COMPANY）已在模型层预留。
- **扩展预留**：用户与企业的关系通过 Employee 解耦；Company 是未来 Knowledge / Room / Agent / Connector 的统一挂载点。

## 路线图

- Knowledge：企业知识空间
- Room：项目/话题工作空间
- Work Event：员工工作过程事件流
- Agent：企业智能体
- Tool / Connector：工具与连接器
