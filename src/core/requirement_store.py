"""File-based requirement store for dev-scheduler."""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml

from src.core.models import Requirement, TaskStatus

logger = structlog.get_logger()


class RequirementStore:
    """Scans, reads, and writes YAML requirement files under memory/plan/."""

    def __init__(self, plan_dir: str = "memory/plan") -> None:
        self._plan_dir = Path(plan_dir)

    def scan_all(self) -> list[Requirement]:
        """Walk memory/plan/**/*.yaml, parse each file into a Requirement."""
        requirements: list[Requirement] = []
        if not self._plan_dir.exists():
            return requirements

        for yaml_file in sorted(self._plan_dir.rglob("*.yaml")):
            try:
                req = self._read_yaml(yaml_file)
                requirements.append(req)
            except Exception as e:
                logger.warning("failed_to_parse_requirement", file=str(yaml_file), error=str(e))

        return requirements

    def get_by_statuses(self, statuses: set[TaskStatus]) -> list[Requirement]:
        """Return requirements whose status is in the given set."""
        return [r for r in self.scan_all() if r.status in statuses]

    def count_by_statuses(self, statuses: set[TaskStatus]) -> int:
        """Count requirements matching the given statuses."""
        return sum(1 for r in self.scan_all() if r.status in statuses)

    def lock(self, req: Requirement, new_status: TaskStatus) -> None:
        """Update the status field in the YAML file in-place."""
        path = Path(req.file_path)
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        data["status"] = new_status.value
        self._write_yaml(path, data)
        logger.info("requirement_locked", file=req.file_path, status=new_status.value)

    def write_result(
        self, req: Requirement, output: str, new_status: TaskStatus
    ) -> None:
        """Write AI output to the appropriate YAML field and update status."""
        path = Path(req.file_path)
        with path.open() as f:
            data = yaml.safe_load(f) or {}

        feature = data.setdefault("feature", {})

        if req.status == TaskStatus.TO_PLAN:
            # Planning output goes into optimized-prompt
            feature["optimized-prompt"] = output
        else:
            # Implementation output goes into action-report
            feature["action-report"] = output

        data["status"] = new_status.value
        self._write_yaml(path, data)
        logger.info(
            "requirement_result_written",
            file=req.file_path,
            status=new_status.value,
        )

    def _read_yaml(self, path: Path) -> Requirement:
        """Parse a YAML file into a Requirement."""
        with path.open() as f:
            data = yaml.safe_load(f) or {}

        # Derive app_name and feature_name from the file path
        # Expected layout: memory/plan/<app-name>/<feature-name>.yaml
        app_name = path.parent.name
        feature_name = path.stem

        raw_status = data.get("status", "Requirement")
        try:
            status = TaskStatus(raw_status)
        except ValueError:
            logger.warning(
                "unknown_status",
                file=str(path),
                status=raw_status,
            )
            status = TaskStatus.REQUIREMENT

        feature = data.get("feature") or {}

        return Requirement(
            file_path=str(path.resolve()),
            app_name=app_name,
            feature_name=feature_name,
            status=status,
            project_path=data.get("path", ""),
            branch=feature.get("branch", ""),
            describe=feature.get("describe", ""),
            optimized_prompt=feature.get("optimized-prompt", ""),
            decision=feature.get("decision") or {},
            action_report=feature.get("action-report", ""),
        )

    def _write_yaml(self, path: Path, data: dict) -> None:
        """Write data back to a YAML file."""
        with path.open("w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
