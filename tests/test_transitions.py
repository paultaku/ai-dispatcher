"""Tests for dev_scheduler.transitions."""

from unittest.mock import MagicMock

from dev_scheduler.claude_runner import ClaudeResult
from dev_scheduler.config import Settings
from dev_scheduler.models import Task, TaskStatus
from dev_scheduler.transitions import TaskProcessor


def _make_settings() -> Settings:
    """Create test settings."""
    return Settings(
        notion_token="test-token",
        notion_database_id="test-db-id",
        max_retries=2,
        retry_backoff_base=0.01,  # Fast retries for tests
    )


def _make_task(status: TaskStatus = TaskStatus.TO_PLAN) -> Task:
    """Create a test task."""
    return Task(
        page_id="page-123",
        name="Test Task",
        status=status,
        description="Test description",
        project_path="/tmp/test-project",
    )


class TestTaskProcessor:
    """Tests for TaskProcessor."""

    def test_process_planning_task_success(self):
        notion = MagicMock()
        claude = MagicMock()
        claude.run_planning.return_value = ClaudeResult(
            success=True, output="## Plan\n1. Do stuff", session_id="sess-123"
        )

        processor = TaskProcessor(notion, claude, _make_settings())
        task = _make_task(TaskStatus.TO_PLAN)

        result = processor.process_task(task)

        assert result is True
        # Should have moved to Planning first
        notion.update_task_status.assert_any_call("page-123", TaskStatus.PLANNING)
        # Then to Planned
        notion.update_task_status.assert_any_call("page-123", TaskStatus.PLANNED)
        # Should have stored the plan output
        notion.update_task_property.assert_called_once()

    def test_process_implementation_task_success(self):
        notion = MagicMock()
        claude = MagicMock()
        claude.run_implementation.return_value = ClaudeResult(
            success=True, output="Implementation complete"
        )

        processor = TaskProcessor(notion, claude, _make_settings())
        task = _make_task(TaskStatus.READY_TO_IMPLEMENT)

        result = processor.process_task(task)

        assert result is True
        notion.update_task_status.assert_any_call(
            "page-123", TaskStatus.IMPLEMENT_IN_PROGRESS
        )
        notion.update_task_status.assert_any_call(
            "page-123", TaskStatus.IMPLEMENT_DONE
        )

    def test_process_task_failure_with_retry(self):
        notion = MagicMock()
        claude = MagicMock()
        claude.run_planning.return_value = ClaudeResult(
            success=False, output="", error="Claude failed"
        )

        processor = TaskProcessor(notion, claude, _make_settings())
        task = _make_task(TaskStatus.TO_PLAN)

        result = processor.process_task(task)

        assert result is False
        # Should have retried (max_retries=2)
        assert claude.run_planning.call_count == 2
        # Should have added error comment
        notion.add_comment.assert_called()

    def test_process_non_actionable_task(self):
        notion = MagicMock()
        claude = MagicMock()

        processor = TaskProcessor(notion, claude, _make_settings())
        task = _make_task(TaskStatus.REQUIREMENT)

        result = processor.process_task(task)

        assert result is False
        claude.run_planning.assert_not_called()
        claude.run_implementation.assert_not_called()

    def test_retry_succeeds_on_second_attempt(self):
        notion = MagicMock()
        claude = MagicMock()
        claude.run_planning.side_effect = [
            ClaudeResult(success=False, output="", error="Temporary failure"),
            ClaudeResult(success=True, output="Plan", session_id="sess-456"),
        ]

        processor = TaskProcessor(notion, claude, _make_settings())
        task = _make_task(TaskStatus.TO_PLAN)

        result = processor.process_task(task)

        assert result is True
        assert claude.run_planning.call_count == 2
