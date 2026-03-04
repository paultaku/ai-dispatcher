"""State machine and transition logic for dev-scheduler."""

from __future__ import annotations

import asyncio

import structlog

from src.core.config import Settings
from src.core.models import (
    AI_TRANSITIONS,
    Requirement,
    TaskStatus,
)
from src.core.requirement_store import RequirementStore
from src.runner.base import BaseRunner, RunnerResult

logger = structlog.get_logger()


class TransitionError(Exception):
    """Raised when a requirement transition fails."""


class TaskProcessor:
    """Processes AI-actionable requirements through their transitions."""

    def __init__(
        self,
        store: RequirementStore,
        runner: BaseRunner,
        settings: Settings,
    ) -> None:
        self._store = store
        self._runner = runner
        self._max_retries = settings.max_retries
        self._backoff_base = settings.retry_backoff_base

    async def process_requirement(self, req: Requirement) -> bool:
        """Process a single AI-actionable requirement. Returns True if successful."""
        transition = AI_TRANSITIONS.get(req.status)
        if not transition:
            logger.warning(
                "no_transition",
                feature=req.feature_name,
                status=req.status.value,
            )
            return False

        in_progress_status, done_status = transition
        original_status = req.status

        log = logger.bind(
            feature=req.feature_name,
            app=req.app_name,
            from_status=req.status.value,
            to_status=done_status.value,
        )

        # Lock: move to in-progress status
        log.info("starting_ai_task")
        self._store.lock(req, in_progress_status)

        # Run AI with retries
        result = await self._run_with_retries(req)

        if result.success:
            log.info("ai_task_completed")
            self._store.write_result(req, result.output, done_status)
            return True
        else:
            log.error("ai_task_failed", error=result.error)
            # Revert to original trigger status so scheduler can retry later
            try:
                self._store.lock(req, original_status)
                log.info(
                    "reverted_to_trigger_status",
                    reverted_to=original_status.value,
                )
            except Exception as e:
                log.error("failed_to_revert_status", error=str(e))
            return False

    async def _run_with_retries(self, req: Requirement) -> RunnerResult:
        """Run the AI runner with retry logic."""
        last_result = RunnerResult(success=False, output="", error="No attempts made")

        for attempt in range(1, self._max_retries + 1):
            logger.info(
                "ai_attempt",
                feature=req.feature_name,
                attempt=attempt,
                max_retries=self._max_retries,
            )

            if req.status == TaskStatus.TO_PLAN:
                last_result = await self._runner.run_planning(req)
            elif req.status == TaskStatus.READY_TO_IMPLEMENT:
                last_result = await self._runner.run_implementation(req)
            else:
                last_result = RunnerResult(
                    success=False,
                    output="",
                    error=f"Unknown AI stage: {req.status}",
                )

            if last_result.success:
                return last_result

            if attempt < self._max_retries:
                wait_time = self._backoff_base ** attempt
                logger.info("retrying", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)

        return last_result
