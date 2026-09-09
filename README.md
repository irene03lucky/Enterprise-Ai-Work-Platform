# Enterprise AI Work Platform（EAI）

面向企业内部的 AI 工作平台。目标不是替代飞书、钉钉等办公软件，而是在企业已有办公体系之上建立一个 **AI 工作层**，让 AI 理解企业组织、企业知识、企业项目与员工工作过程。

当前版本：**V4 · EAI-T04 Project Agent + Task / Follow-up 最小闭环**

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

### V3（T03）：Project Room + Work Event
- **Project Room**：项目工作空间，聚合成员、关联知识文档、工作事件与 Timeline
- **Work Event**：员工工作过程事件流（会议/工作日志/客户反馈/决策/任务进展/文档更新）
- **Room 上下文**：项目信息 + 成员 + 关联文档 + Timeline 自动注入 AI 对话

### V4（T04）：Project Agent + Task / Follow-up
- **Project Agent**：面向项目的 AI 代理，可调用项目信息、Room 上下文、Work Event / Timeline、关联 Knowledge 文档与 Task
  - 项目状态总结 / 最近变化总结 / 风险识别 / 待处理事项查询
  - LangGraph ReAct Agent（模型支持 tool-calling 时），小模型自动降级为「结构化上下文 + 意图识别」确定性链路
- **Task**：轻量任务对象（标题/描述/项目/负责人/截止日期/状态/来源/创建人），状态 `TODO → IN_PROGRESS → DONE`
- **对话 → Task 三段式意图**：
  | 类型 | 示例 | AI 行为 |
  | --- | --- | --- |
  | 信息查询 | 「项目现在怎么样？」 | 直接回答，**不生成任务** |
  | 明确行动要求 | 「让李四周五前完成测试」 | 抽取任务信息 → 生成提案 → **确认后**创建 |
  | Follow-up | 「上线以后告诉我」 | 创建后续跟进事项，保留来源与项目关联 |
- **Room 联动**：待办事项 / 我的任务 / 已完成任务三个视图，Task 保留 `source`、`source_quote`、`source_event_id` 便于追溯
- **AI 代理边界**：AI 可查询、总结、识别、建议；不自动替员工做业务决策、不自动对外承诺、不自动修改项目关键状态、不自动发送外部通知；涉及行动的 Task 默认需人工确认

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
│   │   ├── models/           # SQLAlchemy 模型（含 Knowledge/Room/Task）
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务逻辑层（document_parser / rag_service / agent_service / project_agent_service / task_service）
│   │   ├── main.py           # FastAPI 入口
│   │   └── seed.py           # 演示数据（幂等，含默认知识空间与示例文档）
│   ├── tests/                # pytest（CRUD / 知识库 / Agent 问答 / Room / Task / Project Agent 端到端）
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

测试覆盖：API 启动、数据库连接、Company/Department/Employee/Role CRUD、组织树、认证与权限边界、知识空间 CRUD、文档上传→解析→向量化管线、Agent 带来源问答、多轮对话上下文、Project Room 与 Work Event、Task CRUD 与状态流转、AI 提案确认创建、Project Agent 意图识别（查询/行动/跟进）与端到端闭环。

## API 一览（/api/v1）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/v1/health · /api/v1/health/db · /api/v1/health/ai | 健康检查（AI 链路含 Ollama 连通与模型就绪）；另有根路径 `/health` 供容器探活 |
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
| GET/POST | /companies/{id}/rooms/{rid}/tasks | 项目任务列表（按状态排序） / 新建任务 |
| POST | /companies/{id}/rooms/{rid}/tasks/from-proposal | 确认 AI 任务提案并批量创建（保留来源） |
| PATCH/DELETE | /companies/{id}/rooms/{rid}/tasks/{tid} | 更新任务（含状态流转） / 删除任务 |
| GET | /companies/{id}/tasks?scope=my\|all\|done | 我的任务 / 全部 / 已完成 |
| POST | /companies/{id}/rooms/{rid}/chat | **Project Agent** 对话（SSE：status / intent / token / sources / task_proposals / done） |

## 设计说明

- **非 OA**：不包含即时通讯、审批流、考勤、薪资等传统 OA 功能；员工 `status` 是供未来 AI 理解工作状态的信号，不是考勤。
- **权限预留**：本轮只做"企业成员可见性"边界（成员或所有者可访问），完整 RBAC 与 `visibility`（PRIVATE/DEPARTMENT/PROJECT/COMPANY）已在模型层预留。
- **扩展预留**：用户与企业的关系通过 Employee 解耦；Company 是未来 Knowledge / Room / Agent / Connector 的统一挂载点。

## T04 验收闭环

```
会议 / 工作事件（Work Event）
   → Project Agent 理解项目上下文
   → 用户询问「项目现在怎么样？」
   → AI 依据 Timeline + 任务正确总结（不生成任务）
   → 用户说「让李四周五前完成测试」
   → AI 识别行动要求，抽取负责人/时间并请求确认（此刻未创建任何任务）
   → 用户点击「确认创建」
   → Task 落库（source=CHAT，保留原文摘录）
   → Room 中可查看（待办事项 / 我的任务 / 已完成）、更新状态、标记完成
```

## 路线图

- Knowledge：企业知识空间
- Room：项目/话题工作空间
- Work Event：员工工作过程事件流
- Agent：企业智能体
- Tool / Connector：工具与连接器
