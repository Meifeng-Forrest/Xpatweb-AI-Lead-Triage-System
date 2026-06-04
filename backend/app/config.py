from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Lead Triage API"
    environment: str = Field(default="local", alias="ENVIRONMENT")
    database_url: str = Field(
        default="postgresql+asyncpg://triage:change_me_in_production@postgres:5432/lead_triage",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")
    llm_api_protocol: str = Field(default="openai", alias="LLM_API_PROTOCOL")
    llm_base_url: str = Field(default="https://api.moonshot.cn/v1", alias="LLM_BASE_URL")
    llm_model_extract: str = Field(default="kimi-k2.6", alias="LLM_MODEL_EXTRACT")
    llm_model_triage: str = Field(default="kimi-k2.6", alias="LLM_MODEL_TRIAGE")
    llm_model_draft: str = Field(default="kimi-k2.6", alias="LLM_MODEL_DRAFT")
    kimi_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("KIMI_API_KEY", "MINIMAX_API_KEY"),
    )
    kimi_base_url: str = Field(default="https://api.moonshot.cn/v1", alias="KIMI_BASE_URL")
    kimi_model: str = Field(default="kimi-k2.6", alias="KIMI_MODEL")
    shengsuanyun_api_key: str = Field(default="", alias="SHENGSUANYUN_API_KEY")
    shengsuanyun_base_url: str = Field(
        default="https://router.shengsuanyun.com/api/v1",
        alias="SHENGSUANYUN_BASE_URL",
    )
    shengsuanyun_model: str = Field(default="google/gemini-3-flash", alias="SHENGSUANYUN_MODEL")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com",
        alias="GEMINI_BASE_URL",
    )
    gemini_model_triage: str = Field(default="gemini-3-flash-preview", alias="GEMINI_MODEL_TRIAGE")
    gemini_model_extract: str = Field(default="gemini-3.5-flash", alias="GEMINI_MODEL_EXTRACT")
    gemini_model_score: str = Field(default="gemini-3.5-flash", alias="GEMINI_MODEL_SCORE")
    gemini_model_draft: str = Field(default="gemini-3.5-flash", alias="GEMINI_MODEL_DRAFT")
    gemini_model_research: str = Field(
        default="gemini-3.1-pro-preview",
        alias="GEMINI_MODEL_RESEARCH",
    )
    ms_tenant_id: str = Field(default="", alias="MS_TENANT_ID")
    ms_client_id: str = Field(default="", alias="MS_CLIENT_ID")
    ms_client_secret: str = Field(default="", alias="MS_CLIENT_SECRET")
    mailbox_xp: str = Field(default="", alias="MAILBOX_XP")
    mailbox_risa: str = Field(default="", alias="MAILBOX_RISA")
    mailbox_vls: str = Field(default="", alias="MAILBOX_VLS")
    mailbox_smv: str = Field(default="", alias="MAILBOX_SMV")

    @property
    def configured_mailbox_count(self) -> int:
        return sum(
            bool(value)
            for value in [self.mailbox_xp, self.mailbox_risa, self.mailbox_vls, self.mailbox_smv]
        )

    @property
    def llm_api_key_configured(self) -> bool:
        return bool(self.kimi_api_key or self.shengsuanyun_api_key or self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
