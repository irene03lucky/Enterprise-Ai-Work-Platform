#!/usr/bin/env bash
# =============================================================
# EAI AutoDL 离线部署 - 一次性环境安装脚本
# 用法：把整个项目上传到 /root/autodl-tmp/eai 后执行
#   bash deploy/autodl/setup.sh
# =============================================================
set -e

EAI_DIR="${EAI_DIR:-/root/autodl-tmp/eai}"
DATA_DIR="/root/autodl-tmp/eai-data"

# 自动生成强随机凭据（幂等：重跑不改变已有 .env）
SECRET_KEY="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
PG_PASSWORD="$(openssl rand -hex 16 2>/dev/null || head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"

echo "==> [1/7] AutoDL 学术加速（下载用，失败可忽略）"
source /etc/network_turbo 2>/dev/null || true

echo "==> [2/7] 系统依赖"
apt-get update -y
apt-get install -y curl ca-certificates postgresql postgresql-contrib nginx
# Node 20（Next.js 14 需要 >= 18.17）
if ! command -v node >/dev/null || [ "$(node -v | cut -dv -f2 | cut -d. -f1)" -lt 18 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

echo "==> [3/7] Ollama + 模型（GPU 推理，模型目录固定到持久盘）"
if ! command -v ollama >/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
# 模型放 /root/autodl-tmp（持久盘），避免撑爆系统盘 + 重启丢失
mkdir -p /root/autodl-tmp/ollama-models
if [ -d /etc/systemd/system ]; then
  mkdir -p /etc/systemd/system/ollama.service.d
  cat > /etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
Environment="OLLAMA_MODELS=/root/autodl-tmp/ollama-models"
EOF
  systemctl daemon-reload 2>/dev/null || true
fi
export OLLAMA_MODELS=/root/autodl-tmp/ollama-models
systemctl enable ollama 2>/dev/null || true
systemctl restart ollama 2>/dev/null || (nohup ollama serve >/root/autodl-tmp/ollama.log 2>&1 &)
sleep 3
# 默认对话模型（可按需增删；后端模型注册表会自动发现全部已安装模型）
ollama pull qwen2.5:7b || echo "!! 模型拉取失败，可稍后手动 ollama pull"
# 向量模型（Knowledge RAG 必需：文档解析后用它向量化入库）
ollama pull bge-m3 || echo "!! bge-m3 拉取失败，请手动执行：ollama pull bge-m3"

echo "==> [4/7] PostgreSQL 初始化（数据落 autodl-tmp）"
# 关键：若 .env 已存在（脚本重跑），必须复用其中的密码建库，
# 否则新建的随机密码写不进 .env，会导致「password authentication failed」。
if [ -f "$EAI_DIR/backend/.env" ]; then
  EXISTING_PW="$(grep '^POSTGRES_PASSWORD=' "$EAI_DIR/backend/.env" | cut -d= -f2-)"
  [ -n "$EXISTING_PW" ] && PG_PASSWORD="$EXISTING_PW"
fi
mkdir -p "$DATA_DIR/pg"
systemctl enable postgresql 2>/dev/null || true
systemctl start  postgresql 2>/dev/null || service postgresql start 2>/dev/null || pg_ctlcluster 14 main start 2>/dev/null || pg_ctlcluster 15 main start 2>/dev/null || pg_ctlcluster 16 main start 2>/dev/null
# AutoDL 容器无 sudo，用 su 切 postgres 用户
su -s /bin/bash postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='eai'\"" | grep -q 1 || \
  su -s /bin/bash postgres -c "psql -c \"CREATE USER eai WITH PASSWORD '$PG_PASSWORD';\""
su -s /bin/bash postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='eai'\"" | grep -q 1 || \
  su -s /bin/bash postgres -c "psql -c \"CREATE DATABASE eai OWNER eai;\""

echo "==> [5/7] 后端 Python 环境"
cd "$EAI_DIR/backend"
# AutoDL 为 conda 环境：venv 的 python 常出现「断链符号链接」（ls 看得到但执行报
# No such file or directory），因此这里检测可用性，不可用则直接装进 conda python。
python3 -m venv .venv 2>/dev/null || true
if [ -x .venv/bin/python ]; then
  PY=./.venv/bin/python
else
  echo "   venv 不可用（断链），改用 conda python"
  PY=python3
fi
$PY -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
$PY -c "import uvicorn, fastapi, langchain; print('   依赖自检通过')"

echo "==> [6/7] 前端构建（先在下方填入 AutoDL 自定义服务公网地址）"
# AutoDL 控制台 -> 自定义服务 开通后，会得到类似：
#   https://xxxxx-6006.se.autodl.com
# 把它填到 export PUBLIC_BASE_URL=... 再重跑本脚本，或手动执行本步。
if [ -n "$PUBLIC_BASE_URL" ]; then
  cd "$EAI_DIR/frontend"
  # 注意：前端 getApiBase() 会自己追加 /api/v1，这里只传源地址（不带 /api），
  # 否则会出现 /api/api/v1 双重前缀导致所有请求 404。
  export NEXT_PUBLIC_API_URL="${PUBLIC_BASE_URL%/}"
  npm install --registry=https://registry.npmmirror.com
  npm run build
else
  echo "!! 跳过前端构建：未设置 PUBLIC_BASE_URL（AutoDL 自定义服务地址）"
  echo "   设置后执行：PUBLIC_BASE_URL=https://xxxxx-6006.se.autodl.com bash deploy/autodl/setup.sh"
fi

echo "==> [7/7] 生成后端 .env（生产凭据）"
if [ ! -f "$EAI_DIR/backend/.env" ]; then
  cat > "$EAI_DIR/backend/.env" <<EOF
# ===== 生产配置（务必修改密码/密钥）=====
# JWT 签名密钥：部署时自动生成随机值
SECRET_KEY=$SECRET_KEY

POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=eai
POSTGRES_PASSWORD=$PG_PASSWORD
POSTGRES_DB=eai

# LLM：本地 Ollama（模型注册表自动发现全部已安装模型）
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen2.5:7b

# 向量模型（与 Chroma 存量一致，勿随意更换）
EMBEDDING_MODEL=bge-m3

# RAG / 向量数据（落持久盘）
CHROMA_DIR=$DATA_DIR/chroma
UPLOAD_DIR=$DATA_DIR/uploads

# Agent 编排：auto（支持 tool-calling 的模型走 ReAct，小模型自动降级 RAG）
AGENT_MODE=auto

# 生产关闭演示数据种子
SEED_ON_STARTUP=0
EOF
fi

echo ""
echo "✅ 环境安装完成。下一步："
echo "   1) 修改 $EAI_DIR/backend/.env 中的密码/密钥"
echo "   2) PUBLIC_BASE_URL=... bash deploy/autodl/setup.sh  （补前端构建）"
echo "   3) bash deploy/autodl/start.sh 启动全部服务"
