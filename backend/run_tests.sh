#!/bin/sh
# 在 backend 容器内运行 pytest（AI 模型经 host.docker.internal 访问宿主 Ollama）
docker compose exec -e TEST_DATABASE_URI=postgresql://eai:eai_dev_password@db:5432/eai_test backend python -m pytest tests/ -v "$@"
