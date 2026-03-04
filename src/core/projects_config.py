"""Project registry loader for dev-scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ProjectEntry:
    """A single project entry from projects.yaml."""

    name: str
    path: str
    git_remote: str = ""


class ProjectsConfig:
    """Loads and provides access to the projects.yaml registry."""

    def __init__(self, config_file: str = "projects.yaml") -> None:
        self._config_file = Path(config_file)
        self._projects: dict[str, ProjectEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self._config_file.exists():
            return
        with self._config_file.open() as f:
            data = yaml.safe_load(f) or {}
        for entry in data.get("projects", []):
            name = entry.get("name", "")
            if name:
                self._projects[name] = ProjectEntry(
                    name=name,
                    path=entry.get("path", ""),
                    git_remote=entry.get("git_remote", ""),
                )

    def get(self, name: str) -> ProjectEntry | None:
        """Return the project entry for the given name, or None."""
        return self._projects.get(name)

    def all(self) -> list[ProjectEntry]:
        """Return all registered projects."""
        return list(self._projects.values())
