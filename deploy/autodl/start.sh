#!/usr/bin/env bash
# =============================================================
# EAI AutoDL 离线部署 - 服务启动/停止脚本
#   bash deploy/autodl/start.sh   # 启动全部
#   bash deploy/autodl/start.sh stop
# 单公网口架构（AutoDL 自定义服务 6006）：
#   nginx :6006 ── /api/v1/* ──> uvicorn :8000
#               └─ 其余     ──> Next.js :3000
# =============================================================
set -e

EAI_DIR="${EAI_DIR:-/root/autodl-tmp/eai}"
RUN_DIR="$EAI_DIR/run"
mkdir -p "$RUN_DIR"

# 时区：实例默认 UTC，会让「今日日程 / 当前时间」等按天计算错位
export TZ="${TZ:-Asia/Shanghai}"

if [ "$1" = "stop" ]; then
  for f in nginx backend frontend; do
    [ -f "$RUN_DIR/$f.pid" ] && kill "$(cat "$RUN_DIR/$f.pid")" 2>/dev/null && rm "$RUN_DIR/$f.pid" && echo "stopped $f"
  done
  exit 0
fi

echo "==> [1/5] PostgreSQL"
service postgresql start 2>/dev/null || systemctl start postgresql 2>/dev/null || pg_ctlcluster 14 main start 2>/dev/null || pg_ctlcluster 15 main start 2>/dev/null || true

echo "==> [2/5] Ollama"
export OLLAMA_MODELS=/root/autodl-tmp/ollama-models
mkdir -p "$OLLAMA_MODELS"
systemctl start ollama 2>/dev/null || { pgrep -f "ollama serve" >/dev/null || OLLAMA_MODELS=$OLLAMA_MODELS nohup ollama serve >/root/autodl-tmp/ollama.log 2>&1 & }
sleep 2

echo "==> [3/5] 后端 uvicorn :8000"
# 关键：必须 cd 进 backend 目录再启动——pydantic-settings 按「当前目录」找 .env，
# 在上级目录用 --app-dir 启动会读不到 backend/.env（表现为 DB 密码认证失败）。
cd "$EAI_DIR/backend"
# AutoDL 是 conda 环境，conda 的 python 优先级高于 venv，
# 因此使用 venv 解释器的绝对路径；venv 断链时回退 conda/system python。
PY="$EAI_DIR/backend/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1
nohup "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$RUN_DIR/backend.log" 2>&1 &
echo $! > "$RUN_DIR/backend.pid"

echo "==> [4/5] 前端 Next.js :3000"
cd "$EAI_DIR/frontend"
# 先按进程名清理旧实例，避免 EADDRINUSE（PID 文件可能已过期）
pkill -f "next start" 2>/dev/null || true
pkill -f "next-server" 2>/dev/null || true
sleep 1
nohup npm run start -- -p 3000 > "$RUN_DIR/frontend.log" 2>&1 &
echo $! > "$RUN_DIR/frontend.pid"

echo "==> [5/5] nginx 反向代理 :6006（AutoDL 自定义服务口）"
cp "$EAI_DIR/deploy/autodl/nginx-eai.conf" /etc/nginx/sites-available/eai
ln -sf /etc/nginx/sites-available/eai /etc/nginx/sites-enabled/eai
rm -f /etc/nginx/sites-enabled/default
nginx -t
# 注意：容器内 systemctl / service 常「假成功」（返回 0 却并没起进程），
# 例如对未运行的 nginx 执行 reload。因此不看返回值，直接校验 6006 是否真的在监听。
systemctl restart nginx 2>/dev/null || service nginx start 2>/dev/null || true
sleep 1
if ! ss -tlnp 2>/dev/null | grep -q ':6006'; then
  nginx -s stop 2>/dev/null || true
  nohup nginx -g "daemon off;" > "$RUN_DIR/nginx.log" 2>&1 &
  echo $! > "$RUN_DIR/nginx.pid"
  sleep 2
fi
ss -tlnp 2>/dev/null | grep -q ':6006' \
  && echo "   nginx 已监听 :6006" \
  || echo "!! nginx 未监听 :6006，请查看 $RUN_DIR/nginx.log"

sleep 4
echo ""
echo "✅ 全部服务已启动。健康检查："
echo "   后端:  curl http://127.0.0.1:8000/api/v1/health"
echo "   前端:  curl -I http://127.0.0.1:3000"
echo "   公网:  浏览器打开 AutoDL 自定义服务地址（6006 映射）"
echo "   日志:  $RUN_DIR/{backend,frontend,nginx}.log"
