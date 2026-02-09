"""Main scheduler loop for dev-scheduler."""

from __future__ import annotations

import asyncio
import signal

import structlog

from dev_scheduler.claude_runner import ClaudeRunner
from dev_scheduler.config import Settings
from dev_scheduler.models import AI_TRIGGER_STATUSES
from dev_scheduler.notion_client import NotionTaskClient
from dev_scheduler.transitions import TaskProcessor

logger = structlog.get_logger()


class Scheduler:
    """Polls Notion for AI-actionable tasks and processes them."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._notion = NotionTaskClient(settings)
        self._claude = ClaudeRunner(settings)
        self._processor = TaskProcessor(self._notion, self._claude, settings)
        self._running = False

    async def run(self) -> None:
        """Run the scheduler polling loop."""
        self._running = True
        logger.info(
            "scheduler_started",
            poll_interval=self._settings.poll_interval,
            database_id=self._settings.notion_database_id,
        )

        while self._running:
            try:
                await self._poll_cycle()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("poll_cycle_error", error=str(e))

            # Wait for next poll interval
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

        # Query for all AI-actionable tasks
        tasks = self._notion.query_actionable_tasks(AI_TRIGGER_STATUSES)

        if not tasks:
            logger.debug("no_actionable_tasks")
            return

        logger.info("found_actionable_tasks", count=len(tasks))

        # Process tasks serially (v1 - one at a time)
        for task in tasks:
            if not self._running:
                break

            logger.info("processing_task", task=task.name, status=task.status.value)
            success = self._processor.process_task(task)

            if success:
                logger.info("task_processed", task=task.name)
            else:
                logger.warning("task_failed", task=task.name)


def create_scheduler() -> Scheduler:
    """Create a scheduler instance with settings from environment."""
    settings = Settings()

    # Configure structlog
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

    # Set up signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, scheduler.stop)

    try:
        loop.run_until_complete(scheduler.run())
    finally:
        loop.close()
