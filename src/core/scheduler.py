"""Main scheduler loop for dev-scheduler."""

from __future__ import annotations

import asyncio
import signal

import structlog

from src.core.config import Settings
from src.core.models import AI_TRIGGER_STATUSES, CAPACITY_STATUSES
from src.core.requirement_store import RequirementStore
from src.core.transitions import TaskProcessor
from src.runner.claude import ClaudeRunner

logger = structlog.get_logger()


class Scheduler:
    """Polls the file-based requirement store and processes AI-actionable requirements."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._store = RequirementStore(settings.plan_dir)
        self._runner = ClaudeRunner(settings)
        self._processor = TaskProcessor(self._store, self._runner, settings)
        self._running = False

    async def run(self) -> None:
        """Run the scheduler polling loop."""
        self._running = True
        logger.info(
            "scheduler_started",
            poll_interval=self._settings.poll_interval,
            plan_dir=self._settings.plan_dir,
            max_concurrent=self._settings.max_concurrent,
        )

        while self._running:
            try:
                await self._poll_cycle()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("poll_cycle_error", error=str(e))

            try:
                await asyncio.sleep(self._settings.poll_interval)
            except asyncio.CancelledError:
                break

        logger.info("scheduler_stopped")

    def stop(self) -> None:
        """Signal the scheduler to stop."""
        logger.info("scheduler_stopping")
        self._running = False

    async def _poll_cycle(self) -> None:
        """Execute a single poll cycle."""
        logger.debug("poll_cycle_start")

        # Capacity check: how many AI tasks are currently active?
        active = self._store.count_by_statuses(CAPACITY_STATUSES)
        if active >= self._settings.max_concurrent:
            logger.info("at_capacity", active=active, max=self._settings.max_concurrent)
            return

        # Fetch ToPlan + ReadyToImplement requirements
        candidates = self._store.get_by_statuses(AI_TRIGGER_STATUSES)
        if not candidates:
            logger.debug("no_actionable_requirements")
            return

        logger.info("found_actionable_requirements", count=len(candidates))

        # Process up to (max_concurrent - active) requirements
        slots = self._settings.max_concurrent - active
        for req in candidates[:slots]:
            if not self._running:
                break
            logger.info(
                "processing_requirement",
                feature=req.feature_name,
                app=req.app_name,
                status=req.status.value,
            )
            success = await self._processor.process_requirement(req)
            if success:
                logger.info("requirement_processed", feature=req.feature_name)
            else:
                logger.warning("requirement_failed", feature=req.feature_name)


def create_scheduler() -> Scheduler:
    """Create a Scheduler instance with settings from environment."""
    settings = Settings()

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.stdlib.NAME_TO_LEVEL.get(settings.log_level.lower(), 20)
        ),
    )

    return Scheduler(settings)


def run_with_signal_handling() -> None:
    """Run the scheduler with graceful shutdown on SIGINT/SIGTERM."""
    scheduler = create_scheduler()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, scheduler.stop)

    try:
        loop.run_until_complete(scheduler.run())
    finally:
        loop.close()
