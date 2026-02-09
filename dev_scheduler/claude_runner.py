"""Claude Code CLI runner for dev-scheduler."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import structlog

from dev_scheduler.config import Settings
from dev_scheduler.models import Task

logger = structlog.get_logger()


@dataclass
class ClaudeResult:
    """Result from a Claude Code CLI invocation."""

    success: bool
    output: str
    session_id: str = ""
    error: str = ""


class ClaudeRunner:
    """Invokes Claude Code CLI for AI-driven task processing."""

    def __init__(self, settings: Settings) -> None:
        self._command = settings.claude_command
        self._timeout = settings.claude_timeout
        self._allowed_tools = settings.claude_allowed_tools

    def run_planning(self, task: Task) -> ClaudeResult:
        """Run Claude Code for the planning stage."""
        prompt = self._build_planning_prompt(task)
        return self._run_claude(prompt, task.project_path, task.session_id)

    def run_implementation(self, task: Task) -> ClaudeResult:
        """Run Claude Code for the implementation stage."""
        prompt = self._build_implementation_prompt(task)
        return self._run_claude(prompt, task.project_path, task.session_id)

    def _build_planning_prompt(self, task: Task) -> str:
        """Build the prompt for the planning stage."""
        return (
            f"You are planning the implementation for a development task.\n\n"
            f"## Task: {task.name}\n\n"
            f"## Description:\n{task.description}\n\n"
            f"## Instructions:\n"
            f"1. Analyze the requirements described above\n"
            f"2. Create a detailed implementation plan\n"
            f"3. Identify the files that need to be created or modified\n"
            f"4. Outline the step-by-step approach\n"
            f"5. Note any potential risks or dependencies\n\n"
            f"Output a clear, structured implementation plan in markdown format."
        )

    def _build_implementation_prompt(self, task: Task) -> str:
        """Build the prompt for the implementation stage."""
        plan_section = ""
        if task.plan_output:
            plan_section = f"## Plan:\n{task.plan_output}\n\n"

        return (
            f"You are implementing a development task.\n\n"
            f"## Task: {task.name}\n\n"
            f"## Description:\n{task.description}\n\n"
            f"{plan_section}"
            f"## Instructions:\n"
            f"1. Implement the task according to the description and plan above\n"
            f"2. Write clean, well-structured code\n"
            f"3. Follow existing code conventions in the project\n"
            f"4. Add appropriate error handling\n"
            f"5. Ensure the implementation is complete and functional\n\n"
            f"Implement the changes now."
        )

    def _run_claude(
        self, prompt: str, project_path: str, session_id: str = ""
    ) -> ClaudeResult:
        """Execute Claude Code CLI and capture the result."""
        cmd = [
            self._command,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--allowedTools",
            self._allowed_tools,
        ]

        if session_id:
            cmd.extend(["--resume", session_id])

        # Validate and resolve project path
        cwd = self._resolve_project_path(project_path)

        logger.info(
            "running_claude",
            cwd=str(cwd) if cwd else None,
            has_session=bool(session_id),
            prompt_length=len(prompt),
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=self._timeout,
            )

            if result.returncode != 0:
                error_msg = result.stderr or f"Claude exited with code {result.returncode}"
                logger.error("claude_failed", error=error_msg, returncode=result.returncode)
                return ClaudeResult(
                    success=False,
                    output="",
                    error=error_msg,
                )

            # Parse JSON response
            try:
                response = json.loads(result.stdout)
                return ClaudeResult(
                    success=True,
                    output=response.get("result", result.stdout),
                    session_id=response.get("session_id", ""),
                )
            except json.JSONDecodeError:
                # If JSON parsing fails, return raw output
                return ClaudeResult(
                    success=True,
                    output=result.stdout,
                )

        except subprocess.TimeoutExpired:
            logger.error("claude_timeout", timeout=self._timeout)
            return ClaudeResult(
                success=False,
                output="",
                error=f"Claude Code timed out after {self._timeout}s",
            )
        except FileNotFoundError:
            logger.error("claude_not_found", command=self._command)
            return ClaudeResult(
                success=False,
                output="",
                error=f"Claude Code CLI not found: {self._command}",
            )

    @staticmethod
    def _resolve_project_path(project_path: str) -> str | None:
        """Validate and resolve a project path to prevent directory traversal."""
        if not project_path:
            return None

        resolved = Path(project_path).resolve()

        # Must be an existing directory
        if not resolved.is_dir():
            raise ValueError(f"Project path does not exist or is not a directory: {resolved}")

        # Must not contain suspicious path components
        path_str = str(resolved)
        if "\x00" in path_str:
            raise ValueError("Project path contains null bytes")

        return str(resolved)
