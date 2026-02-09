"""Tests for dev_scheduler.scheduler."""

import asyncio
from unittest.mock import MagicMock

import pytest

from dev_scheduler.config import Settings
from dev_scheduler.models import Task, TaskStatus
from dev_scheduler.scheduler import Scheduler


def _make_settings() -> Settings:
    return Settings(
        notion_token="test-token",
        notion_database_id="test-db-id",
        poll_interval=1,
    )


class TestScheduler:
    """Tests for Scheduler."""

    @pytest.mark.asyncio
    async def test_poll_cycle_no_tasks(self):
        settings = _make_settings()
        scheduler = Scheduler(settings)
        scheduler._notion = MagicMock()
        scheduler._notion.query_actionable_tasks.return_value = []

        await scheduler._poll_cycle()

        scheduler._notion.query_actionable_tasks.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_cycle_with_tasks(self):
        settings = _make_settings()
        scheduler = Scheduler(settings)
        scheduler._notion = MagicMock()
        scheduler._processor = MagicMock()

        task = Task(
            page_id="page-1",
            name="Test",
            status=TaskStatus.TO_PLAN,
        )
        scheduler._notion.query_actionable_tasks.return_value = [task]
        scheduler._processor.process_task.return_value = True

        scheduler._running = True
        await scheduler._poll_cycle()

        scheduler._processor.process_task.assert_called_once_with(task)

    @pytest.mark.asyncio
    async def test_stop_scheduler(self):
        settings = _make_settings()
        scheduler = Scheduler(settings)
        scheduler._notion = MagicMock()
        scheduler._notion.query_actionable_tasks.return_value = []

        # Start scheduler and stop it after a short delay
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            scheduler.stop()

        task = asyncio.create_task(stop_after_delay())
        await scheduler.run()
        await task

        assert scheduler._running is False
