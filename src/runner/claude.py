"""Claude Code runner for dev-scheduler using the Agent SDK."""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

from claude_agent_sdk import (
    CLIConnectionError,
    CLINotFoundError,
    ClaudeAgentOptions,
    ProcessError,
    ResultMessage,
    SystemMessage,
    query,
)

from src.core.config import Settings
from src.core.models import Requirement, TaskStatus
from src.runner.base import BaseRunner, RunnerResult

logger = structlog.get_logger()


class ClaudeRunner(BaseRunner):
    """Invokes Claude Code via the Agent SDK for AI-driven requirement processing."""

    def __init__(self, settings: Settings) -> None:
        self._timeout = settings.claude_timeout
        self._allowed_tools = settings.claude_allowed_tools

    async def run_planning(self, req: Requirement) -> RunnerResult:
        """Run Claude Code for the planning stage."""
        prompt = self._build_planning_prompt(req)
        return await self._run_claude(prompt, req.project_path)

    async def run_implementation(self, req: Requirement) -> RunnerResult:
        """Run Claude Code for the implementation stage."""
        prompt = self._build_implementation_prompt(req)
        return await self._run_claude(prompt, req.project_path)

    def _build_planning_prompt(self, req: Requirement) -> str:
        """Build a ralplan-style planning prompt."""
        return (
            f"You are planning the implementation for a software feature.\n\n"
            f"## Feature: {req.feature_name}\n"
            f"## App: {req.app_name}\n\n"
            f"## Description:\n{req.describe}\n\n"
            f"## Your task:\n"
            f"1. Analyze the requirements described above\n"
            f"2. Generate an optimized implementation prompt that another AI agent "
            f"can use to implement this feature without ambiguity\n"
            f"3. List key decisions or questions with clear answers\n"
            f"4. Produce a step-by-step implementation plan\n\n"
            f"Output format (markdown):\n"
            f"```\n"
            f"## Optimized Prompt\n"
            f"<concise, actionable prompt for the implementation agent>\n\n"
            f"## Decisions\n"
            f"<question>: <answer>\n"
            f"...\n\n"
            f"## Implementation Plan\n"
            f"1. <step>\n"
            f"...\n"
            f"```\n"
        )

    def _build_implementation_prompt(self, req: Requirement) -> str:
        """Build a ralph-style implementation prompt."""
        decision_section = ""
        if req.decision:
            lines = [f"- {k}: {v}" for k, v in req.decision.items()]
            decision_section = "## Key Decisions:\n" + "\n".join(lines) + "\n\n"

        prompt_content = req.optimized_prompt or req.describe

        branch_section = ""
        if req.branch:
            branch_section = (
                f"## Branch:\n"
                f"Implement on branch `{req.branch}`. "
                f"Create it from the current HEAD if it does not exist.\n\n"
            )

        return (
            f"You are implementing a software feature.\n\n"
            f"## Feature: {req.feature_name}\n"
            f"## App: {req.app_name}\n\n"
            f"## Implementation Prompt:\n{prompt_content}\n\n"
            f"{decision_section}"
            f"{branch_section}"
            f"## Instructions:\n"
            f"1. Implement the feature according to the prompt and decisions above\n"
            f"2. Write clean, well-structured code following existing conventions\n"
            f"3. Add appropriate error handling\n"
            f"4. Ensure the implementation is complete and functional\n"
            f"5. Commit your changes with a descriptive commit message\n\n"
            f"Implement the feature now."
        )

    async def _run_claude(self, prompt: str, project_path: str) -> RunnerResult:
        """Execute Claude Code via the Agent SDK and capture the result."""
        cwd = self._resolve_project_path(project_path)

        logger.info(
            "running_claude",
            cwd=cwd,
            prompt_length=len(prompt),
        )

        options = ClaudeAgentOptions(
            allowed_tools=self._allowed_tools,
            permission_mode="bypassPermissions",
            max_turns=30,
        )

        if cwd:
            options.cwd = cwd

        try:
            async with asyncio.timeout(self._timeout):
                result_output = ""

                async for message in query(prompt=prompt, options=options):
                    if isinstance(message, ResultMessage):
                        result_output = message.result

                return RunnerResult(success=True, output=result_output)

        except TimeoutError:
            logger.error("claude_timeout", timeout=self._timeout)
            return RunnerResult(
                success=False,
                output="",
                error=f"Claude Code timed out after {self._timeout}s",
            )
        except CLINotFoundError:
            logger.error("claude_not_found")
            return RunnerResult(
                success=False,
                output="",
                error="Claude Code CLI not found. Install with: pip install claude-agent-sdk",
            )
        except (CLIConnectionError, ProcessError) as e:
            logger.error("claude_error", error=str(e))
            return RunnerResult(success=False, output="", error=str(e))

    @staticmethod
    def _resolve_project_path(project_path: str) -> str | None:
        """Validate and resolve a project path."""
        if not project_path:
            return None

        resolved = Path(project_path).resolve()

        if not resolved.is_dir():
            raise ValueError(
                f"Project path does not exist or is not a directory: {resolved}"
            )

        path_str = str(resolved)
        if "\x00" in path_str:
            raise ValueError("Project path contains null bytes")

        return str(resolved)
