"""Data models for dev-scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    """14-stage workflow status for development tasks."""

    # Human stages
    REQUIREMENT = "Requirement"
    DESIGN_IN_PROGRESS = "DesignInProgress"

    # AI Planning stages
    TO_PLAN = "ToPlan"
    PLANNING = "Planning"
    PLANNED = "Planned"

    # AI Implementation stages
    READY_TO_IMPLEMENT = "ReadyToImplement"
    IMPLEMENT_IN_PROGRESS = "ImplementInProgress"
    IMPLEMENT_DONE = "ImplementDone"

    # Human Review stages
    READY_TO_REVIEW = "ReadyToReview"
    REVIEW_IN_PROGRESS = "ReviewInProgress"
    REVIEW_DONE = "ReviewDone"

    # Release stages
    READY_TO_RELEASE = "ReadyToRelease"
    RELEASE_IN_PROGRESS = "ReleaseInProgress"
    RELEASE_DONE = "ReleaseDone"


# Statuses that the scheduler should pick up and process via AI
AI_TRIGGER_STATUSES: set[TaskStatus] = {
    TaskStatus.TO_PLAN,
    TaskStatus.READY_TO_IMPLEMENT,
}

# Map: trigger status -> (in-progress status, done status)
AI_TRANSITIONS: dict[TaskStatus, tuple[TaskStatus, TaskStatus]] = {
    TaskStatus.TO_PLAN: (TaskStatus.PLANNING, TaskStatus.PLANNED),
    TaskStatus.READY_TO_IMPLEMENT: (
        TaskStatus.IMPLEMENT_IN_PROGRESS,
        TaskStatus.IMPLEMENT_DONE,
    ),
}

# All valid forward transitions
VALID_TRANSITIONS: dict[TaskStatus, TaskStatus] = {
    TaskStatus.REQUIREMENT: TaskStatus.DESIGN_IN_PROGRESS,
    TaskStatus.DESIGN_IN_PROGRESS: TaskStatus.TO_PLAN,
    TaskStatus.TO_PLAN: TaskStatus.PLANNING,
    TaskStatus.PLANNING: TaskStatus.PLANNED,
    TaskStatus.PLANNED: TaskStatus.READY_TO_IMPLEMENT,
    TaskStatus.READY_TO_IMPLEMENT: TaskStatus.IMPLEMENT_IN_PROGRESS,
    TaskStatus.IMPLEMENT_IN_PROGRESS: TaskStatus.IMPLEMENT_DONE,
    TaskStatus.IMPLEMENT_DONE: TaskStatus.READY_TO_REVIEW,
    TaskStatus.READY_TO_REVIEW: TaskStatus.REVIEW_IN_PROGRESS,
    TaskStatus.REVIEW_IN_PROGRESS: TaskStatus.REVIEW_DONE,
    TaskStatus.REVIEW_DONE: TaskStatus.READY_TO_RELEASE,
    TaskStatus.READY_TO_RELEASE: TaskStatus.RELEASE_IN_PROGRESS,
    TaskStatus.RELEASE_IN_PROGRESS: TaskStatus.RELEASE_DONE,
}


@dataclass
class Task:
    """Represents a task from the Notion database."""

    page_id: str
    name: str
    status: TaskStatus
    description: str = ""
    project_path: str = ""
    repository: str = ""
    branch: str = ""
    plan_output: str = ""
    error: str = ""
    session_id: str = ""  # Claude Code session ID for --resume
    raw_properties: dict = field(default_factory=dict)
