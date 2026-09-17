#!/bin/bash
# =============================================================
# EAI 本地服务 - 一键停止（数据保留，下次启动仍在）
# =============================================================
set -u

PROJECT_DIR="/Users/116130077qq.com/Desktop/Enterprise AI Work Platform（EAI）"

cd "$PROJECT_DIR" 2>/dev/null || {
  echo "[错误] 找不到项目目录：$PROJECT_DIR"
  read -r -p "按回车键关闭此窗口…" _
  exit 1
}

echo "正在停止 EAI 容器…"
docker compose stop
echo ""
docker compose ps --format "{{.Name}}  {{.Status}}" 2>/dev/null
echo ""
echo "已停止（数据卷保留，下次启动数据还在）。"
echo "此窗口可以直接关闭。"
