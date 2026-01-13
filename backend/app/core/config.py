"""
Application configuration using Pydantic Settings.
Loads configuration from environment variables.
"""
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Settings
    app_name: str = Field(default="Ollama Chat Application")
    debug: bool = Field(default=False)
    log_level: str = Field(default="info")

    # Database Settings - Either provide DATABASE_URL or individual components
    database_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection URL (takes precedence over individual components)",
    )
    postgres_user: str = Field(default="postgres", description="PostgreSQL user")
    postgres_password: str = Field(default="postgres", description="PostgreSQL password")
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_db: str = Field(default="ollama_chat", description="PostgreSQL database name")

    # Ollama Settings
    ollama_base_url: str = Field(
        default="http://host.docker.internal:11434",
        description="Base URL for Ollama API",
    )
    default_model: str = Field(
        default="mistral:7b",
        description="Default Ollama model to use",
    )

    # Title Generation Settings
    title_generation_model: str = Field(
        default="SummLlama3.2:3B-Q5_K_M",
        description="Model to use for chat title generation",
    )
    title_generation_prompt_file: str = Field(
        default="app/prompts/chat_title_generation.md",
        description="Path to prompt file for title generation (relative to backend directory)",
    )
    enable_auto_title: bool = Field(
        default=True,
        description="Enable automatic chat title generation",
    )

    # CORS Settings
    cors_origins: Union[List[str], str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins (comma-separated string or list)",
    )

    # Security Settings
    secret_key: str = Field(
        default="",
        description="Secret key for JWT tokens (required in production)",
    )

    def model_post_init(self, __context) -> None:
        """Validate settings after initialization."""
        if not self.debug and not self.secret_key:
            raise ValueError(
                "SECRET_KEY environment variable is required when DEBUG=false. "
                "Generate one with: openssl rand -hex 32"
            )

    @field_validator("database_url", mode="before")
    @classmethod
    def build_database_url(cls, v, info):
        """Build database URL from components if not provided."""
        # If DATABASE_URL is explicitly provided, use it
        if v:
            return v

        # Otherwise, build from individual components
        data = info.data
        user = data.get("postgres_user", "postgres")
        password = data.get("postgres_password", "postgres")
        host = data.get("postgres_host", "localhost")
        port = data.get("postgres_port", 5432)
        db = data.get("postgres_db", "ollama_chat")

        # Construct PostgreSQL async URL
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v if isinstance(v, list) else [v]

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["debug", "info", "warning", "error", "critical"]
        v_lower = v.lower()
        if v_lower not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of {valid_levels}")
        return v_lower


# Create global settings instance
settings = Settings()
