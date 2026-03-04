"""Tests for src.core.requirement_store."""

import textwrap
from pathlib import Path

import pytest
import yaml

from src.core.models import TaskStatus
from src.core.requirement_store import RequirementStore


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _read_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f) or {}


class TestRequirementStore:
    """Tests for RequirementStore."""

    def test_scan_all_empty_dir(self, tmp_path):
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        store = RequirementStore(str(plan_dir))
        assert store.scan_all() == []

    def test_scan_all_missing_dir(self, tmp_path):
        store = RequirementStore(str(tmp_path / "nonexistent"))
        assert store.scan_all() == []

    def test_scan_all_parses_yaml(self, tmp_path):
        plan_dir = tmp_path / "plan"
        yaml_file = plan_dir / "myapp" / "my-feature.yaml"
        _write_yaml(yaml_file, {
            "path": "/some/project",
            "status": "ToPlan",
            "feature": {
                "branch": "feature/my-feature",
                "describe": "A cool feature",
                "optimized-prompt": "Do the thing",
                "decision": {"q1": "yes"},
                "action-report": "",
            },
        })

        store = RequirementStore(str(plan_dir))
        reqs = store.scan_all()

        assert len(reqs) == 1
        req = reqs[0]
        assert req.app_name == "myapp"
        assert req.feature_name == "my-feature"
        assert req.status == TaskStatus.TO_PLAN
        assert req.project_path == "/some/project"
        assert req.branch == "feature/my-feature"
        assert req.describe == "A cool feature"
        assert req.optimized_prompt == "Do the thing"
        assert req.decision == {"q1": "yes"}

    def test_scan_all_multiple_apps(self, tmp_path):
        plan_dir = tmp_path / "plan"
        _write_yaml(plan_dir / "app1" / "feat-a.yaml", {
            "status": "Requirement",
            "feature": {"describe": "app1 feat a"},
        })
        _write_yaml(plan_dir / "app2" / "feat-b.yaml", {
            "status": "ReadyToImplement",
            "feature": {"describe": "app2 feat b"},
        })

        store = RequirementStore(str(plan_dir))
        reqs = store.scan_all()
        assert len(reqs) == 2
        app_names = {r.app_name for r in reqs}
        assert app_names == {"app1", "app2"}

    def test_get_by_statuses_filters_correctly(self, tmp_path):
        plan_dir = tmp_path / "plan"
        _write_yaml(plan_dir / "app" / "feat1.yaml", {"status": "ToPlan", "feature": {}})
        _write_yaml(plan_dir / "app" / "feat2.yaml", {"status": "Requirement", "feature": {}})
        _write_yaml(plan_dir / "app" / "feat3.yaml", {"status": "ReadyToImplement", "feature": {}})

        store = RequirementStore(str(plan_dir))
        trigger = store.get_by_statuses({TaskStatus.TO_PLAN, TaskStatus.READY_TO_IMPLEMENT})
        assert len(trigger) == 2
        statuses = {r.status for r in trigger}
        assert statuses == {TaskStatus.TO_PLAN, TaskStatus.READY_TO_IMPLEMENT}

    def test_count_by_statuses(self, tmp_path):
        plan_dir = tmp_path / "plan"
        _write_yaml(plan_dir / "app" / "feat1.yaml", {"status": "Planning", "feature": {}})
        _write_yaml(plan_dir / "app" / "feat2.yaml", {"status": "Planning", "feature": {}})
        _write_yaml(plan_dir / "app" / "feat3.yaml", {"status": "Requirement", "feature": {}})

        store = RequirementStore(str(plan_dir))
        count = store.count_by_statuses({TaskStatus.PLANNING})
        assert count == 2

    def test_lock_updates_status(self, tmp_path):
        plan_dir = tmp_path / "plan"
        yaml_file = plan_dir / "app" / "feat.yaml"
        _write_yaml(yaml_file, {"status": "ToPlan", "feature": {"describe": "x"}})

        store = RequirementStore(str(plan_dir))
        reqs = store.scan_all()
        assert len(reqs) == 1
        req = reqs[0]

        store.lock(req, TaskStatus.PLANNING)

        data = _read_yaml(yaml_file)
        assert data["status"] == "Planning"

    def test_write_result_planning_writes_optimized_prompt(self, tmp_path):
        plan_dir = tmp_path / "plan"
        yaml_file = plan_dir / "app" / "feat.yaml"
        _write_yaml(yaml_file, {
            "status": "ToPlan",
            "feature": {"describe": "Build x", "optimized-prompt": ""},
        })

        store = RequirementStore(str(plan_dir))
        reqs = store.scan_all()
        req = reqs[0]

        store.write_result(req, "Optimized prompt text", TaskStatus.PLANNED)

        data = _read_yaml(yaml_file)
        assert data["status"] == "Planned"
        assert data["feature"]["optimized-prompt"] == "Optimized prompt text"

    def test_write_result_implementation_writes_action_report(self, tmp_path):
        plan_dir = tmp_path / "plan"
        yaml_file = plan_dir / "app" / "feat.yaml"
        _write_yaml(yaml_file, {
            "status": "ReadyToImplement",
            "feature": {"describe": "Build x", "action-report": ""},
        })

        store = RequirementStore(str(plan_dir))
        reqs = store.scan_all()
        req = reqs[0]

        store.write_result(req, "Feature was implemented", TaskStatus.IMPLEMENT_DONE)

        data = _read_yaml(yaml_file)
        assert data["status"] == "ImplementDone"
        assert data["feature"]["action-report"] == "Feature was implemented"

    def test_unknown_status_defaults_to_requirement(self, tmp_path):
        plan_dir = tmp_path / "plan"
        yaml_file = plan_dir / "app" / "feat.yaml"
        _write_yaml(yaml_file, {"status": "UnknownStatus", "feature": {}})

        store = RequirementStore(str(plan_dir))
        reqs = store.scan_all()
        assert len(reqs) == 1
        assert reqs[0].status == TaskStatus.REQUIREMENT
