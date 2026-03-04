"""Tests for src.core.models."""

from src.core.models import (
    AI_TRANSITIONS,
    AI_TRIGGER_STATUSES,
    CAPACITY_STATUSES,
    VALID_TRANSITIONS,
    Requirement,
    TaskStatus,
)


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_has_14_statuses(self):
        assert len(TaskStatus) == 14

    def test_status_values(self):
        """Status values must match the YAML format."""
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

    def test_capacity_statuses(self):
        assert TaskStatus.PLANNING in CAPACITY_STATUSES
        assert TaskStatus.IMPLEMENT_IN_PROGRESS in CAPACITY_STATUSES
        assert len(CAPACITY_STATUSES) == 2

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


class TestRequirement:
    """Tests for Requirement dataclass."""

    def test_create_minimal_requirement(self):
        req = Requirement(
            file_path="/tmp/memory/plan/myapp/feat.yaml",
            app_name="myapp",
            feature_name="feat",
            status=TaskStatus.REQUIREMENT,
        )
        assert req.file_path == "/tmp/memory/plan/myapp/feat.yaml"
        assert req.app_name == "myapp"
        assert req.feature_name == "feat"
        assert req.status == TaskStatus.REQUIREMENT
        assert req.project_path == ""
        assert req.branch == ""
        assert req.describe == ""
        assert req.optimized_prompt == ""
        assert req.decision == {}
        assert req.action_report == ""

    def test_create_full_requirement(self):
        req = Requirement(
            file_path="/tmp/memory/plan/app/feature.yaml",
            app_name="app",
            feature_name="feature",
            status=TaskStatus.TO_PLAN,
            project_path="/path/to/project",
            branch="feature/my-feature",
            describe="Build a feature",
            optimized_prompt="Implement X using Y",
            decision={"question1": "What color?", "answer1": "blue"},
            action_report="Feature implemented successfully",
        )
        assert req.project_path == "/path/to/project"
        assert req.branch == "feature/my-feature"
        assert req.describe == "Build a feature"
        assert req.optimized_prompt == "Implement X using Y"
        assert req.decision == {"question1": "What color?", "answer1": "blue"}
        assert req.action_report == "Feature implemented successfully"
