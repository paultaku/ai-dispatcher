"""YAML configuration loader for project directory mappings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger()


@dataclass
class ProjectMapping:
    """Mapping between a project name, Notion database ID, and working directory."""

    name: str
    notion_database_id: str
    working_directory: str


class YamlConfig:
    """YAML configuration loader for project directory mappings."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialize the YAML config loader.

        Args:
            config_path: Path to the YAML configuration file.
        """
        self._mappings: list[ProjectMapping] = []
        self._load(config_path)

    def _load(self, config_path: str) -> None:
        """Load and validate YAML configuration file.

        Args:
            config_path: Path to the YAML configuration file.
        """
        config_file = Path(config_path)

        if not config_file.exists():
            logger.info("config_file_not_found", path=config_path)
            return

        try:
            with config_file.open("r") as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error("yaml_parse_error", path=config_path, error=str(e))
            return

        if not config_data or "projects" not in config_data:
            logger.warning("missing_projects_key", path=config_path)
            return

        projects = config_data["projects"]
        if not isinstance(projects, list):
            logger.warning("projects_not_list", path=config_path)
            return

        seen_database_ids = set()

        for entry in projects:
            if not isinstance(entry, dict):
                logger.warning("invalid_project_entry", entry=entry)
                continue

            # Validate name
            name = entry.get("name")
            if not name or not isinstance(name, str) or not name.strip():
                logger.warning("missing_or_empty_name", entry=entry)
                continue

            # Validate notion_database_id
            notion_database_id = entry.get("notion_database_id")
            if not notion_database_id or not isinstance(notion_database_id, str) or not notion_database_id.strip():
                logger.warning("missing_or_empty_notion_database_id", name=name)
                continue

            # Check for duplicate database IDs
            if notion_database_id in seen_database_ids:
                logger.warning("duplicate_notion_database_id", database_id=notion_database_id, name=name)
                continue

            # Validate working_directory
            working_directory = entry.get("working_directory")
            if not working_directory or not isinstance(working_directory, str) or not working_directory.strip():
                logger.warning("missing_or_empty_working_directory", name=name)
                continue

            # Check if absolute path
            if not os.path.isabs(working_directory):
                logger.warning("working_directory_not_absolute", name=name, path=working_directory)
                continue

            # Check if directory exists
            working_dir_path = Path(working_directory)
            if not working_dir_path.is_dir():
                logger.warning("working_directory_not_found", name=name, path=working_directory)
                continue

            # All validations passed
            seen_database_ids.add(notion_database_id)
            self._mappings.append(
                ProjectMapping(
                    name=name,
                    notion_database_id=notion_database_id,
                    working_directory=working_directory,
                )
            )

        logger.info("config_loaded", mapping_count=len(self._mappings))

    def resolve_working_directory(self, notion_database_id: str) -> str | None:
        """Resolve working directory for a given Notion database ID.

        Args:
            notion_database_id: The Notion database ID to look up.

        Returns:
            The working directory path if found, None otherwise.
        """
        for mapping in self._mappings:
            if mapping.notion_database_id == notion_database_id:
                return mapping.working_directory
        return None

    @property
    def mappings(self) -> list[ProjectMapping]:
        """Return all loaded project mappings."""
        return list(self._mappings)
