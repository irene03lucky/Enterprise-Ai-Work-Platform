# EAI AutoDL 离线部署指南

## 架构

```
浏览器
  │  https://<xxxx>-6006.se.autodl.com   (AutoDL 自定义服务，唯一公网口)
  ▼
nginx :6006
  ├── /api/v1/*  →  uvicorn :8000   (FastAPI + LangGraph + Chroma)
  └── 其余        →  Next.js :3000  (Work Center / Rooms / Calendar / Knowledge / Organization)

内部依赖：
  PostgreSQL（/root/autodl-tmp/eai-data/pg）
  Ollama + qwen2.5:7b 等 GPU 模型（模型注册表自动发现，用户可在 AI 助手切换）
  Chroma 向量库（/root/autodl-tmp/eai-data/chroma）
```

## 部署步骤

1. **上传代码**到实例：`/root/autodl-tmp/eai`（autodl-tmp 为持久盘，重启不丢）
2. **一次性安装**：
   ```bash
   cd /root/autodl-tmp/eai
   bash deploy/autodl/setup.sh
   ```
3. **修改凭据**：编辑 `backend/.env`，改 `POSTGRES_PASSWORD`
4. **开通 AutoDL 自定义服务**（控制台 → 自定义服务），得到公网地址，如
   `https://xxxxx-6006.se.autodl.com`
5. **补前端构建**（把公网地址烘焙进前端）：
   ```bash
   PUBLIC_BASE_URL=https://xxxxx-6006.se.autodl.com bash deploy/autodl/setup.sh
   ```
6. **启动**：`bash deploy/autodl/start.sh`
7. 浏览器打开公网地址注册/登录使用

## 常用运维

| 操作 | 命令 |
|---|---|
| 停止全部 | `bash deploy/autodl/start.sh stop` |
| 查看日志 | `/root/autodl-tmp/eai/run/*.log` |
| 增加模型 | `ollama pull <model>`（模型下拉框自动出现） |
| 备份知识库/向量 | 备份 `/root/autodl-tmp/eai-data/` |
| 数据库备份 | `pg_dump -U eai eai > backup.sql` |

## 注意事项

- **生产凭据**：务必修改 `.env` 中的数据库密码；`SKIP_SEED=1` 已关闭演示数据
- **首次使用**：注册第一个账号 → Organization 里建部门/员工 → Knowledge 上传文档 →
  Work Center 即可 RAG 问答
- **Agent 记忆**：MemorySaver 为进程内存活，服务重启后 Agent 多轮记忆清零
  （会话文本仍在 PostgreSQL，不影响历史对话查看；需要跨重启记忆可换 PostgresSaver）
- **AutoDL 重启**：实例重启后执行 `bash deploy/autodl/start.sh` 即可恢复（数据不丢）
