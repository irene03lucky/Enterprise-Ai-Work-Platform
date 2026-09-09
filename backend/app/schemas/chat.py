from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=40)
    # LangGraph 记忆线程 ID（可选；不传则服务端按「企业+用户」兜底生成）
    conversation_id: str | None = Field(default=None, max_length=36)
    # 用户选择的模型（Model Registry 的 model_id；不传用默认模型）
    model_id: str | None = Field(default=None, max_length=100)
