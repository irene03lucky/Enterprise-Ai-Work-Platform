#!/bin/bash
# =============================================================
# EAI 本地一键启动（在 Dock / 桌面双击即可运行）
#   1) 确保 Docker Desktop 与 Ollama 在运行
#   2) 拉起 Docker 全栈（db + backend + frontend）
#   3) 等服务就绪后自动打开浏览器
# 停止服务：docker compose stop（或运行同目录的「停止 EAI.command」）
# =============================================================
set -u

PROJECT_DIR="/Users/116130077qq.com/Desktop/Enterprise AI Work Platform（EAI）"
APP_URL="http://localhost:3000"
API_HEALTH="http://localhost:8000/api/v1/health"
OLLAMA_TAGS="http://127.0.0.1:11434/api/tags"

pause_on_error() {
  echo ""
  read -r -p "按回车键关闭此窗口…" _
}

cd "$PROJECT_DIR" 2>/dev/null || {
  echo "[错误] 找不到项目目录：$PROJECT_DIR"
  echo "       如果项目被移动过，请编辑本文件开头的 PROJECT_DIR。"
  pause_on_error
  exit 1
}

echo "=============================================="
echo " EAI 本地工作平台 - 一键启动"
echo " 项目目录：$PROJECT_DIR"
echo "=============================================="
echo ""

# ---------- 1. Docker Desktop ----------
echo "[1/4] 检查 Docker Desktop"
if docker info >/dev/null 2>&1; then
  echo "      Docker 已在运行"
else
  echo "      Docker 未运行，正在启动（首次约 30~60 秒）…"
  open -a Docker
  for _ in $(seq 1 30); do
    sleep 4
    if docker info >/dev/null 2>&1; then
      echo "      Docker 就绪"
      break
    fi
  done
fi
if ! docker info >/dev/null 2>&1; then
  echo "[错误] Docker 启动超时，请手动打开 Docker Desktop 后重试。"
  pause_on_error
  exit 1
fi

# ---------- 2. Ollama（本地模型服务） ----------
echo "[2/4] 检查 Ollama"
if curl -s --max-time 2 "$OLLAMA_TAGS" >/dev/null 2>&1; then
  echo "      Ollama 已在运行"
else
  echo "      Ollama 未运行，正在启动…"
  open -a Ollama
  for _ in $(seq 1 20); do
    sleep 2
    if curl -s --max-time 2 "$OLLAMA_TAGS" >/dev/null 2>&1; then
      echo "      Ollama 就绪"
      break
    fi
  done
fi
if ! curl -s --max-time 2 "$OLLAMA_TAGS" >/dev/null 2>&1; then
  echo "[提示] Ollama 未就绪：页面可以打开，但 AI 对话与知识库检索会不可用。"
  echo "       请手动打开「Ollama」应用后刷新页面。"
fi

# ---------- 3. 启动容器 ----------
echo "[3/4] 启动 EAI 服务（db / backend / frontend）"
docker compose up -d >/dev/null 2>&1
docker compose ps --format "      {{.Name}}  {{.Status}}" 2>/dev/null

# ---------- 4. 等待就绪并打开页面 ----------
echo "[4/4] 等待服务就绪"
READY=0
for _ in $(seq 1 30); do
  if curl -s --max-time 3 "$API_HEALTH" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done

echo ""
if [ "$READY" = "1" ]; then
  echo "服务已就绪，正在打开浏览器…"
  open "$APP_URL"
  echo ""
  echo "  访问地址：$APP_URL"
  echo "  演示账号：zhangsan@eai.dev / demo1234   （管理员：admin@eai.dev / admin123）"
else
  echo "[警告] 后端未在预期时间内就绪，最近日志如下："
  docker compose logs backend --tail=15 2>/dev/null
  echo ""
  echo "  你仍可尝试访问：$APP_URL"
fi
echo ""
echo "此窗口可以直接关闭（关闭窗口不会停止服务）。"
