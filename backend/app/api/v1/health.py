"""健康检查。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "eai-backend"}


@router.get("/health/db")
def health_check_db(db: Annotated[Session, Depends(get_db)]):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return {"status": "error", "database": "unreachable"}
    return {"status": "ok", "database": "connected"}


@router.get("/health/ai")
def health_check_ai():
    """AI 链路健康检查：Ollama 服务与已安装模型。"""
    import json
    import urllib.request

    from app.core.config import settings

    result = {
        "provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "ollama_url": settings.OLLAMA_BASE_URL,
        "ollama_reachable": False,
        "models_installed": [],
        "llm_ready": False,
        "embedding_ready": False,
    }
    try:
        with urllib.request.urlopen(
            f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3
        ) as resp:
            models = json.loads(resp.read().decode()).get("models", [])
            names = [m.get("model") or m.get("name", "") for m in models]
            result["models_installed"] = names
            result["ollama_reachable"] = True
            result["llm_ready"] = any(n.startswith(settings.LLM_MODEL) for n in names)
            result["embedding_ready"] = any(
                n.startswith(settings.EMBEDDING_MODEL) for n in names
            )
    except Exception:
        pass
    return result
