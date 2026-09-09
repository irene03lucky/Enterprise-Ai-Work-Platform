#!/usr/bin/env bash
# =============================================================
# EAI AutoDL 离线部署 - 服务启动/停止脚本
#   bash deploy/autodl/start.sh   # 启动全部
#   bash deploy/autodl/start.sh stop
# 单公网口架构（AutoDL 自定义服务 6006）：
#   Caddy :6006 ── /api/v1/* ──> uvicorn :8000
#              └─ 其余     ──> Next.js :3000
# =============================================================
set -e

EAI_DIR="${EAI_DIR:-/root/autodl-tmp/eai}"
RUN_DIR="$EAI_DIR/run"
mkdir -p "$RUN_DIR"

if [ "$1" = "stop" ]; then
  for f in caddy backend frontend; do
    [ -f "$RUN_DIR/$f.pid" ] && kill "$(cat "$RUN_DIR/$f.pid")" 2>/dev/null && rm "$RUN_DIR/$f.pid" && echo "stopped $f"
  done
  exit 0
fi

echo "==> [1/5] PostgreSQL"
systemctl start postgresql 2>/dev/null || pg_ctlcluster 16 main start 2>/dev/null || pg_ctlcluster 15 main start 2>/dev/null || true

echo "==> [2/5] Ollama"
systemctl start ollama 2>/dev/null || { pgrep -f "ollama serve" >/dev/null || nohup ollama serve >/root/autodl-tmp/ollama.log 2>&1 & }
sleep 2

echo "==> [3/5] 后端 uvicorn :8000"
cd "$EAI_DIR/backend"
source .venv/bin/activate
[ -f "$RUN_DIR/backend.pid" ] && kill "$(cat "$RUN_DIR/backend.pid")" 2>/dev/null || true
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$RUN_DIR/backend.log" 2>&1 &
echo $! > "$RUN_DIR/backend.pid"

echo "==> [4/5] 前端 Next.js :3000"
cd "$EAI_DIR/frontend"
[ -f "$RUN_DIR/frontend.pid" ] && kill "$(cat "$RUN_DIR/frontend.pid")" 2>/dev/null || true
nohup npm run start -- -p 3000 > "$RUN_DIR/frontend.log" 2>&1 &
echo $! > "$RUN_DIR/frontend.pid"

echo "==> [5/5] Caddy 反向代理 :6006（AutoDL 自定义服务口）"
cp "$EAI_DIR/deploy/autodl/Caddyfile" "$RUN_DIR/Caddyfile"
[ -f "$RUN_DIR/caddy.pid" ] && kill "$(cat "$RUN_DIR/caddy.pid")" 2>/dev/null || true
nohup caddy run --config "$RUN_DIR/Caddyfile" > "$RUN_DIR/caddy.log" 2>&1 &
echo $! > "$RUN_DIR/caddy.pid"

sleep 4
echo ""
echo "✅ 全部服务已启动。健康检查："
echo "   后端:  curl http://127.0.0.1:8000/api/v1/health"
echo "   前端:  curl -I http://127.0.0.1:3000"
echo "   公网:  浏览器打开 AutoDL 自定义服务地址（6006 映射）"
echo "   日志:  $RUN_DIR/{backend,frontend,caddy}.log"
