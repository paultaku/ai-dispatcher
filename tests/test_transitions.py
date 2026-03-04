"""Tests for src.core.transitions."""

from unittest.mock import MagicMock, AsyncMock

import pytest

from src.core.config import Settings
from src.core.models import Requirement, TaskStatus
from src.core.transitions import TaskProcessor
from src.runner.base import RunnerResult


def _make_settings() -> Settings:
    """Create test settings."""
    return Settings(
        max_retries=2,
        retry_backoff_base=0.01,  # Fast retries for tests
    )


def _make_requirement(status: TaskStatus = TaskStatus.TO_PLAN) -> Requirement:
    """Create a test requirement."""
    return Requirement(
        file_path="/tmp/memory/plan/myapp/feat.yaml",
        app_name="myapp",
        feature_name="feat",
        status=status,
        project_path="/tmp/test-project",
        describe="Test description",
    )


class TestTaskProcessor:
    """Tests for TaskProcessor."""

    @pytest.mark.asyncio
    async def test_process_planning_requirement_success(self):
        store = MagicMock()
        runner = MagicMock()
        runner.run_planning = AsyncMock(
            return_value=RunnerResult(success=True, output="## Plan\n1. Do stuff")
        )

        processor = TaskProcessor(store, runner, _make_settings())
        req = _make_requirement(TaskStatus.TO_PLAN)

        result = await processor.process_requirement(req)

        assert result is True
        # Should have locked to Planning first
        store.lock.assert_any_call(req, TaskStatus.PLANNING)
        # Should have written result with Planned status
        store.write_result.assert_called_once_with(
            req, "## Plan\n1. Do stuff", TaskStatus.PLANNED
        )

    @pytest.mark.asyncio
    async def test_process_implementation_requirement_success(self):
        store = MagicMock()
        runner = MagicMock()
        runner.run_implementation = AsyncMock(
            return_value=RunnerResult(success=True, output="Implementation complete")
        )

        processor = TaskProcessor(store, runner, _make_settings())
        req = _make_requirement(TaskStatus.READY_TO_IMPLEMENT)

        result = await processor.process_requirement(req)

        assert result is True
        store.lock.assert_any_call(req, TaskStatus.IMPLEMENT_IN_PROGRESS)
        store.write_result.assert_called_once_with(
            req, "Implementation complete", TaskStatus.IMPLEMENT_DONE
        )

    @pytest.mark.asyncio
    async def test_process_requirement_failure_with_retry(self):
        store = MagicMock()
        runner = MagicMock()
        runner.run_planning = AsyncMock(
            return_value=RunnerResult(success=False, output="", error="Runner failed")
        )

        processor = TaskProcessor(store, runner, _make_settings())
        req = _make_requirement(TaskStatus.TO_PLAN)

        result = await processor.process_requirement(req)

        assert result is False
        # Should have retried (max_retries=2)
        assert runner.run_planning.call_count == 2
        # Should have reverted to original trigger status
        store.lock.assert_any_call(req, TaskStatus.TO_PLAN)

    @pytest.mark.asyncio
    async def test_process_non_actionable_requirement(self):
        store = MagicMock()
        runner = MagicMock()

        processor = TaskProcessor(store, runner, _make_settings())
        req = _make_requirement(TaskStatus.REQUIREMENT)

        result = await processor.process_requirement(req)

        assert result is False
        runner.run_planning.assert_not_called()
        runner.run_implementation.assert_not_called()
        store.lock.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self):
        store = MagicMock()
        runner = MagicMock()
        runner.run_planning = AsyncMock(
            side_effect=[
                RunnerResult(success=False, output="", error="Temporary failure"),
                RunnerResult(success=True, output="Plan"),
            ]
        )

        processor = TaskProcessor(store, runner, _make_settings())
        req = _make_requirement(TaskStatus.TO_PLAN)

        result = await processor.process_requirement(req)

        assert result is True
        assert runner.run_planning.call_count == 2
        store.write_result.assert_called_once_with(req, "Plan", TaskStatus.PLANNED)

    @pytest.mark.asyncio
    async def test_process_implementation_failure_reverts_status(self):
        store = MagicMock()
        runner = MagicMock()
        runner.run_implementation = AsyncMock(
            return_value=RunnerResult(
                success=False, output="", error="Implementation failed"
            )
        )

        processor = TaskProcessor(store, runner, _make_settings())
        req = _make_requirement(TaskStatus.READY_TO_IMPLEMENT)

        result = await processor.process_requirement(req)

        assert result is False
        # Should have locked to in-progress first
        store.lock.assert_any_call(req, TaskStatus.IMPLEMENT_IN_PROGRESS)
        # Should have reverted to original trigger status
        store.lock.assert_any_call(req, TaskStatus.READY_TO_IMPLEMENT)
