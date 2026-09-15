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

# ---------- 缓存/临时目录重定向到持久盘 ----------
# AutoDL 系统盘只有 30GB：pip / npm 缓存与临时文件默认写在系统盘，
# 装依赖（pip 约 2GB + npm 缓存数 GB）时极易把系统盘撑爆导致脚本中途失败。
PERSIST="/root/autodl-tmp"
export PIP_CACHE_DIR="$PERSIST/caches/pip"
export NPM_CONFIG_CACHE="$PERSIST/caches/npm"
export TMPDIR="$PERSIST/tmp"
export OLLAMA_MODELS="$PERSIST/ollama-models"
mkdir -p "$PIP_CACHE_DIR" "$NPM_CONFIG_CACHE" "$TMPDIR" "$OLLAMA_MODELS"

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
# 已在运行则不重复拉起（否则会打印端口占用错误）
systemctl restart ollama 2>/dev/null || { pgrep -f "ollama serve" >/dev/null || nohup ollama serve >/root/autodl-tmp/ollama.log 2>&1 & }
sleep 3
# 默认对话模型（可按需增删；后端模型注册表会自动发现全部已安装模型）
# 已存在则跳过：重跑脚本时避免再次走外网下载（内网模型可离线导入）
ollama list 2>/dev/null | grep -q '^qwen2.5:7b' || \
  ollama pull qwen2.5:7b || echo "!! 模型拉取失败，可稍后手动 ollama pull"
# 向量模型（Knowledge RAG 必需：文档解析后用它向量化入库）
ollama list 2>/dev/null | grep -q '^bge-m3' || \
  ollama pull bge-m3 || echo "!! bge-m3 拉取失败，可用 ModelScope 的 GGUF 离线导入（见 README）"

echo "==> [4/7] PostgreSQL 初始化"
# 关键：若 .env 已存在（脚本重跑），必须复用其中的密码建库，
# 否则新建的随机密码写不进 .env，会导致「password authentication failed」。
if [ -f "$EAI_DIR/backend/.env" ]; then
  EXISTING_PW="$(grep '^POSTGRES_PASSWORD=' "$EAI_DIR/backend/.env" | cut -d= -f2-)"
  [ -n "$EXISTING_PW" ] && PG_PASSWORD="$EXISTING_PW"
fi
# 说明：PostgreSQL 集群数据目录仍在系统盘（/var/lib/postgresql）。
# 业务库体积很小（MB 级），暂不迁移以降低部署风险；
# 若后续数据量显著增长，再把该目录迁到 $DATA_DIR/pg 并在 postgresql.conf 改 data_directory。
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

echo "==> [6/7] 前端构建"
cd "$EAI_DIR/frontend"
npm install --registry=https://registry.npmmirror.com
# 前端 getApiBase() 会自己追加 /api/v1：
#  - 默认用「同源相对地址」/api/v1：请求发往当前页面所在域名，经 nginx :6006 代理到后端，
#    因此公网地址 / SSH 隧道 / 反向代理下都自动可用，换访问方式无需重新构建；
#  - 显式给了 PUBLIC_BASE_URL 时则烘焙绝对地址（注意不带 /api 后缀，否则会
#    变成 /api/api/v1 双重前缀导致全部请求 404）。
if [ -n "$PUBLIC_BASE_URL" ]; then
  export NEXT_PUBLIC_API_URL="${PUBLIC_BASE_URL%/}"
  echo "   使用绝对地址: $NEXT_PUBLIC_API_URL"
else
  export NEXT_PUBLIC_API_URL=""
  echo "   使用同源相对地址 /api/v1（推荐：公网地址与 SSH 隧道通用）"
fi
npm run build

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
echo "   1) bash $EAI_DIR/deploy/autodl/start.sh   启动全部服务"
echo "   2) 首次部署播种演示数据："
echo "      cd $EAI_DIR/backend && python3 -c \"from app.seed import run_seed; run_seed()\""
echo "   3) 查看凭据：cat $EAI_DIR/backend/.env"
