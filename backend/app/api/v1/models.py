"""Model Registry API：AI 助手可选模型列表（管理员允许范围内的模型）。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai import model_registry
from app.api.deps import get_current_user
from app.core.config import settings
from app.models import User

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
def list_available_models(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """可用模型列表（Ollama 本机已安装模型 + 配置默认）。

    前端用它渲染「当前模型」下拉框；用户选择后随对话请求回传 model_id。
    """
    return {
        "models": model_registry.list_models(),
        "default": settings.LLM_MODEL,
        "provider": settings.LLM_PROVIDER,
    }
