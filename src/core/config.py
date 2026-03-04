"""Configuration management for dev-scheduler."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # File-based store
    plan_dir: str = "memory/plan"
    projects_file: str = "projects.yaml"

    # Scheduler
    poll_interval: int = 300        # 5 minutes between polls
    max_concurrent: int = 3         # capacity limit for concurrent AI tasks
    max_retries: int = 2            # max retries per AI stage
    retry_backoff_base: float = 2.0 # exponential backoff base

    # Claude Code
    claude_timeout: int = 600       # 10 min timeout for AI operations
    claude_allowed_tools: list[str] = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]

    # Logging
    log_level: str = "INFO"
