"""State machine and transition logic for dev-scheduler."""

from __future__ import annotations

import time

import structlog

from dev_scheduler.claude_runner import ClaudeResult, ClaudeRunner
from dev_scheduler.config import Settings
from dev_scheduler.models import (
    AI_TRANSITIONS,
    Task,
    TaskStatus,
)
from dev_scheduler.notion_client import NotionTaskClient

logger = structlog.get_logger()


class TransitionError(Exception):
    """Raised when a task transition fails."""


class TaskProcessor:
    """Processes AI-actionable tasks through their transitions."""

    def __init__(
        self,
        notion: NotionTaskClient,
        claude: ClaudeRunner,
        settings: Settings,
    ) -> None:
        self._notion = notion
        self._claude = claude
        self._max_retries = settings.max_retries
        self._backoff_base = settings.retry_backoff_base

    def process_task(self, task: Task) -> bool:
        """Process a single AI-actionable task. Returns True if successful."""
        transition = AI_TRANSITIONS.get(task.status)
        if not transition:
            logger.warning("no_transition", task=task.name, status=task.status.value)
            return False

        in_progress_status, done_status = transition

        log = logger.bind(
            task=task.name,
            page_id=task.page_id,
            from_status=task.status.value,
            to_status=done_status.value,
        )

        # Move to in-progress
        log.info("starting_ai_task")
        self._notion.update_task_status(task.page_id, in_progress_status)

        # Run AI with retries
        result = self._run_with_retries(task)

        if result.success:
            log.info("ai_task_completed")
            # Store output if it was a planning task
            if task.status == TaskStatus.TO_PLAN and result.output:
                try:
                    self._notion.update_task_property(
                        task.page_id, "PlanOutput", result.output[:2000]
                    )
                except Exception as e:
                    log.warning("failed_to_store_plan", error=str(e))

            # Store session_id as comment for potential resume
            if result.session_id:
                try:
                    self._notion.add_comment(
                        task.page_id,
                        f"[dev-scheduler] Session ID: {result.session_id}",
                    )
                except Exception as e:
                    log.warning("failed_to_store_session", error=str(e))

            # Move to done status
            self._notion.update_task_status(task.page_id, done_status)
            return True
        else:
            log.error("ai_task_failed", error=result.error)
            # Add error comment to Notion
            try:
                self._notion.add_comment(
                    task.page_id,
                    f"[dev-scheduler] Error: {result.error}",
                )
            except Exception:
                pass
            return False

    def _run_with_retries(self, task: Task) -> ClaudeResult:
        """Run Claude Code with retry logic."""
        last_result = ClaudeResult(success=False, output="", error="No attempts made")

        for attempt in range(1, self._max_retries + 1):
            logger.info(
                "ai_attempt",
                task=task.name,
                attempt=attempt,
                max_retries=self._max_retries,
            )

            if task.status == TaskStatus.TO_PLAN:
                last_result = self._claude.run_planning(task)
            elif task.status == TaskStatus.READY_TO_IMPLEMENT:
                last_result = self._claude.run_implementation(task)
            else:
                last_result = ClaudeResult(
                    success=False, output="", error=f"Unknown AI stage: {task.status}"
                )

            if last_result.success:
                return last_result

            # Exponential backoff before retry
            if attempt < self._max_retries:
                wait_time = self._backoff_base ** attempt
                logger.info("retrying", wait_seconds=wait_time)
                time.sleep(wait_time)

        return last_result
