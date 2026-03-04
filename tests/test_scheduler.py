"""Tests for src.core.scheduler."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.config import Settings
from src.core.models import Requirement, TaskStatus
from src.core.scheduler import Scheduler


def _make_settings() -> Settings:
    return Settings(
        poll_interval=1,
        max_concurrent=3,
    )


def _make_requirement(status: TaskStatus = TaskStatus.TO_PLAN) -> Requirement:
    return Requirement(
        file_path="/tmp/memory/plan/app/feat.yaml",
        app_name="app",
        feature_name="feat",
        status=status,
    )


class TestScheduler:
    """Tests for Scheduler."""

    @pytest.mark.asyncio
    async def test_poll_cycle_no_requirements(self):
        settings = _make_settings()
        scheduler = Scheduler(settings)
        scheduler._store = MagicMock()
        scheduler._store.count_by_statuses.return_value = 0
        scheduler._store.get_by_statuses.return_value = []

        await scheduler._poll_cycle()

        scheduler._store.get_by_statuses.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_cycle_at_capacity(self):
        settings = _make_settings()
        scheduler = Scheduler(settings)
        scheduler._store = MagicMock()
        scheduler._store.count_by_statuses.return_value = 3  # at max_concurrent

        await scheduler._poll_cycle()

        # Should not query for candidates when at capacity
        scheduler._store.get_by_statuses.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_cycle_processes_requirements(self):
        settings = _make_settings()
        scheduler = Scheduler(settings)
        scheduler._store = MagicMock()
        scheduler._processor = MagicMock()

        req = _make_requirement(TaskStatus.TO_PLAN)
        scheduler._store.count_by_statuses.return_value = 0
        scheduler._store.get_by_statuses.return_value = [req]
        scheduler._processor.process_requirement = AsyncMock(return_value=True)

        scheduler._running = True
        await scheduler._poll_cycle()

        scheduler._processor.process_requirement.assert_called_once_with(req)

    @pytest.mark.asyncio
    async def test_poll_cycle_respects_slots(self):
        settings = _make_settings()
        settings2 = Settings(poll_interval=1, max_concurrent=2)
        scheduler = Scheduler(settings2)
        scheduler._store = MagicMock()
        scheduler._processor = MagicMock()

        # 1 active, max 2 → only 1 slot left
        req1 = _make_requirement(TaskStatus.TO_PLAN)
        req2 = _make_requirement(TaskStatus.READY_TO_IMPLEMENT)
        scheduler._store.count_by_statuses.return_value = 1
        scheduler._store.get_by_statuses.return_value = [req1, req2]
        scheduler._processor.process_requirement = AsyncMock(return_value=True)

        scheduler._running = True
        await scheduler._poll_cycle()

        # Should only process 1 (max_concurrent - active = 2 - 1 = 1)
        assert scheduler._processor.process_requirement.call_count == 1

    @pytest.mark.asyncio
    async def test_stop_scheduler(self):
        settings = _make_settings()
        scheduler = Scheduler(settings)
        scheduler._store = MagicMock()
        scheduler._store.count_by_statuses.return_value = 0
        scheduler._store.get_by_statuses.return_value = []

        async def stop_after_delay():
            await asyncio.sleep(0.1)
            scheduler.stop()

        task = asyncio.create_task(stop_after_delay())
        await scheduler.run()
        await task

        assert scheduler._running is False
