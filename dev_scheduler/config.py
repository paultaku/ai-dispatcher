"""Configuration management for dev-scheduler."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Notion API
    notion_token: str
    notion_database_id: str

    # Scheduler
    poll_interval: int = 30  # seconds between polls
    max_retries: int = 2  # max retries per AI stage
    retry_backoff_base: float = 2.0  # exponential backoff base

    # YAML project config
    config_file: str = "config.yaml"

    # Claude Code
    claude_command: str = "claude"
    claude_timeout: int = 600  # 10 min timeout for AI operations
    claude_allowed_tools: str = "Read,Write,Edit,Bash,Glob,Grep"

    # Logging
    log_level: str = "INFO"
