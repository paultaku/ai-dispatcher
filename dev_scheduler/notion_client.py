"""Notion API client for dev-scheduler."""

from __future__ import annotations

import structlog
from notion_client import Client

from dev_scheduler.config import Settings
from dev_scheduler.models import Task, TaskStatus

logger = structlog.get_logger()


class NotionTaskClient:
    """Wrapper around the Notion API for task operations."""

    def __init__(self, settings: Settings) -> None:
        self._client = Client(auth=settings.notion_token)
        self._database_id = settings.notion_database_id
        
        # Retrieve database to get the associated data source ID
        database = self._client.databases.retrieve(self._database_id)
        data_sources = database.get("data_sources", [])
        if not data_sources:
             # Fallback or error if no data source is found, but for now assuming it exists based on exploration
             # In a real scenario we might want to raise an error or handle this gracefully
             # For this fix we'll assume the first one is the correct one as per new API usage
             logger.warning("no_data_source_found", database_id=self._database_id)
             self._data_source_id = None
        else:
             self._data_source_id = data_sources[0]["id"]

    def query_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        """Query the Notion database for tasks with a specific status."""
        logger.info("querying_notion", status=status.value)
        
        if not self._data_source_id:
             logger.error("missing_data_source_id", database_id=self._database_id)
             return []

        response = self._client.data_sources.query(
            data_source_id=self._data_source_id,
            filter={
                "property": "Status",
                "select": {"equals": status.value},
            },
        )
        tasks = []
        for page in response["results"]:
            task = self._page_to_task(page)
            if task:
                tasks.append(task)
        logger.info("query_complete", status=status.value, count=len(tasks))
        return tasks

    def query_actionable_tasks(self, trigger_statuses: set[TaskStatus]) -> list[Task]:
        """Query for all tasks that are in an AI-actionable status."""
        all_tasks: list[Task] = []
        for status in trigger_statuses:
            all_tasks.extend(self.query_tasks_by_status(status))
        return all_tasks

    def update_task_status(self, page_id: str, new_status: TaskStatus) -> None:
        """Update a task's status in Notion."""
        logger.info("updating_status", page_id=page_id, new_status=new_status.value)
        self._client.pages.update(
            page_id=page_id,
            properties={
                "Status": {
                    "select": {"name": new_status.value},
                },
            },
        )

    def add_comment(self, page_id: str, content: str) -> None:
        """Add a comment to a Notion page."""
        logger.info("adding_comment", page_id=page_id)
        self._client.comments.create(
            parent={"page_id": page_id},
            rich_text=[
                {
                    "type": "text",
                    "text": {"content": content[:2000]},  # Notion limit
                }
            ],
        )

    def update_task_property(
        self, page_id: str, property_name: str, value: str
    ) -> None:
        """Update a rich text property on a task page."""
        logger.info(
            "updating_property", page_id=page_id, property_name=property_name
        )
        self._client.pages.update(
            page_id=page_id,
            properties={
                property_name: {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": value[:2000]},
                        }
                    ],
                },
            },
        )

    def _page_to_task(self, page: dict) -> Task | None:
        """Convert a Notion page to a Task object."""
        try:
            props = page["properties"]

            # Extract title (Name property)
            name = ""
            name_prop = props.get("Name", {})
            if name_prop.get("title"):
                name = name_prop["title"][0]["text"]["content"]

            # Extract status
            status_prop = props.get("Status", {})
            # Handle both 'status' and 'select' types for backward compatibility or different setups
            status_name = ""
            if "status" in status_prop:
                status_name = status_prop["status"].get("name", "")
            elif "select" in status_prop:
                status_name = status_prop["select"].get("name", "")
            
            status = TaskStatus(status_name)

            # Extract description (rich text)
            description = self._extract_rich_text(props, "Description")

            # Extract project path
            project_path = self._extract_rich_text(props, "ProjectPath")

            # Extract repository
            repository = ""
            repo_prop = props.get("Repository", {})
            if repo_prop.get("url"):
                repository = repo_prop["url"]
            elif repo_prop.get("rich_text"):
                repository = self._extract_rich_text(props, "Repository")

            # Extract branch
            branch = self._extract_rich_text(props, "Branch")

            # Extract plan output
            plan_output = self._extract_rich_text(props, "PlanOutput")

            return Task(
                page_id=page["id"],
                name=name,
                status=status,
                description=description,
                project_path=project_path,
                repository=repository,
                branch=branch,
                plan_output=plan_output,
                raw_properties=props,
            )
        except (KeyError, ValueError, IndexError) as e:
            logger.warning("failed_to_parse_page", page_id=page.get("id"), error=str(e))
            return None

    @staticmethod
    def _extract_rich_text(props: dict, property_name: str) -> str:
        """Extract plain text from a rich_text property."""
        prop = props.get(property_name, {})
        rich_text = prop.get("rich_text", [])
        if rich_text:
            text = rich_text[0].get("text", {}).get("content", "")
            # Strip null bytes and control characters for safety
            return text.replace("\x00", "")
        return ""
