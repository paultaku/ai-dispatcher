"""Tests for dev_scheduler.models."""

from dev_scheduler.models import (
    AI_TRANSITIONS,
    AI_TRIGGER_STATUSES,
    VALID_TRANSITIONS,
    Task,
    TaskStatus,
)


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_has_14_statuses(self):
        assert len(TaskStatus) == 14

    def test_status_values_match_notion(self):
        """Status values must match exactly what Notion expects."""
        expected = [
            "Requirement",
            "DesignInProgress",
            "ToPlan",
            "Planning",
            "Planned",
            "ReadyToImplement",
            "ImplementInProgress",
            "ImplementDone",
            "ReadyToReview",
            "ReviewInProgress",
            "ReviewDone",
            "ReadyToRelease",
            "ReleaseInProgress",
            "ReleaseDone",
        ]
        actual = [s.value for s in TaskStatus]
        assert actual == expected

    def test_ai_trigger_statuses(self):
        assert TaskStatus.TO_PLAN in AI_TRIGGER_STATUSES
        assert TaskStatus.READY_TO_IMPLEMENT in AI_TRIGGER_STATUSES
        assert len(AI_TRIGGER_STATUSES) == 2

    def test_ai_transitions_mapping(self):
        assert AI_TRANSITIONS[TaskStatus.TO_PLAN] == (
            TaskStatus.PLANNING,
            TaskStatus.PLANNED,
        )
        assert AI_TRANSITIONS[TaskStatus.READY_TO_IMPLEMENT] == (
            TaskStatus.IMPLEMENT_IN_PROGRESS,
            TaskStatus.IMPLEMENT_DONE,
        )

    def test_valid_transitions_chain(self):
        """All statuses except the last should have a forward transition."""
        all_statuses = list(TaskStatus)
        for status in all_statuses[:-1]:  # All except ReleaseDone
            assert status in VALID_TRANSITIONS
        assert TaskStatus.RELEASE_DONE not in VALID_TRANSITIONS

    def test_valid_transitions_are_forward(self):
        """Each transition should go to the next status in order."""
        all_statuses = list(TaskStatus)
        for i, status in enumerate(all_statuses[:-1]):
            next_status = VALID_TRANSITIONS[status]
            assert next_status == all_statuses[i + 1]


class TestTask:
    """Tests for Task dataclass."""

    def test_create_minimal_task(self):
        task = Task(
            page_id="abc-123",
            name="Test Task",
            status=TaskStatus.REQUIREMENT,
        )
        assert task.page_id == "abc-123"
        assert task.name == "Test Task"
        assert task.status == TaskStatus.REQUIREMENT
        assert task.description == ""
        assert task.project_path == ""

    def test_create_full_task(self):
        task = Task(
            page_id="abc-123",
            name="Full Task",
            status=TaskStatus.TO_PLAN,
            description="Build a feature",
            project_path="/path/to/project",
            repository="https://github.com/user/repo",
            branch="feature-branch",
        )
        assert task.description == "Build a feature"
        assert task.project_path == "/path/to/project"
        assert task.repository == "https://github.com/user/repo"
        assert task.branch == "feature-branch"
