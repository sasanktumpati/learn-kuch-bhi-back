from typing import Optional
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, RedisDsn


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
    host: str = Field(alias="POSTGRES_HOST")
    port: int = Field(alias="POSTGRES_DB_PORT")
    db_name: str = Field(alias="POSTGRES_DB_NAME")
    user: str = Field(alias="POSTGRES_DB_USER")
    password: str = Field(alias="POSTGRES_DB_PASSWORD")

    @computed_field
    def connection_string(self) -> PostgresDsn:
        return PostgresDsn(
            f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"
        )


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
    host: str = Field(default="localhost", alias="REDIS_HOST")
    port: int = Field(default=6379, alias="REDIS_PORT")
    password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    db: int = Field(default=0, alias="REDIS_DB")
    retries: Optional[int] = Field(default=3, alias="REDIS_RETRIES")
    timeout: Optional[str] = Field(default="1s", alias="REDIS_TIMEOUT")

    @computed_field
    def dsn(self) -> RedisDsn:
        if self.password:
            return RedisDsn(
                f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
            )
        else:
            return RedisDsn(f"redis://{self.host}:{self.port}/{self.db}")


class JWTSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
    issuer: str = Field(default="https://auth.example.com", alias="JWT_ISSUER")
    application_id: str = Field(default="my-app-id", alias="JWT_APPLICATION_ID")
    token_lifetime_seconds: int = Field(
        default=3600, alias="JWT_TOKEN_LIFETIME_SECONDS"
    )


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
    name: str = Field(default="kuch-bhi", alias="APP_NAME")
    version: str = Field(default="v1", alias="API_VERSION")
    port: int = Field(default=9000, alias="APP_PORT")
    mode: str = Field(default="prod", alias="MODE")
    jwt_secret: str = Field(alias="JWT_SECRET")

    @computed_field
    def is_production(self) -> bool:
        return self.mode != "dev"

    @computed_field
    def is_testing(self) -> bool:
        return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=lambda: AppSettings())
    postgres: PostgresSettings = Field(default_factory=lambda: PostgresSettings())
    redis: RedisSettings = Field(default_factory=lambda: RedisSettings())
    jwt: JWTSettings = Field(default_factory=lambda: JWTSettings())

    gemini_api_key: str = Field(default=None, alias="GEMINI_API_KEY")
    openrouter_api_key: str = Field(default=None, alias="OPENROUTER_API_KEY")

    # Model provider selection: "google" or "openrouter"
    model_provider: str = Field(default="google", alias="MODEL_PROVIDER")
    openrouter_model: str = Field(
        default="x-ai/grok-code-fast-1", alias="OPENROUTER_MODEL"
    )

    # Context7 MCP (Model Context Protocol) configuration
    context7_enabled: bool = Field(default=True, alias="CONTEXT7_ENABLED")
    context7_mcp_url: str = Field(
        default="https://mcp.context7.com/mcp", alias="CONTEXT7_MCP_URL"
    )
    context7_api_key: Optional[str] = Field(default=None, alias="CONTEXT7_API_KEY")


settings = Settings()
