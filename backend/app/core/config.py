"""统一环境变量与配置管理。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    POSTGRES_USER: str = "eai"
    POSTGRES_PASSWORD: str = "eai_dev_password"
    POSTGRES_DB: str = "eai"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"

    # Auth
    SECRET_KEY: str = "eai-dev-secret-key-change-me-in-production-32b"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # Startup seeding (Docker 演示数据)
    SEED_ON_STARTUP: bool = False

    # ---------- AI / RAG ----------
    # 生成模型提供方：ollama（本地）| openai-compatible（AutoDL 等）
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:1.5b"
    # 向量模型固定走 Ollama，须与 Chroma 已入库向量保持一致
    EMBEDDING_MODEL: str = "bge-m3"
    # openai-compatible 模式下的端点与密钥
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    # 云端模式下额外可选模型（逗号分隔），用于前端「当前模型」下拉切换；
    # 例如：deepseek-chat,deepseek-reasoner
    LLM_EXTRA_MODELS: str = ""

    # 数据目录（容器内挂载卷）
    CHROMA_DIR: str = "data/chroma"
    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_MB: int = 20

    # Agent 编排：小模型 tool-calling 不可靠时走「先检索后生成」RAG 链
    AGENT_MODE: str = "auto"  # auto | always | never

    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
