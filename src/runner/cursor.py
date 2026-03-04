"""Cursor runner stub for dev-scheduler."""

from __future__ import annotations

from src.core.models import Requirement
from src.runner.base import BaseRunner, RunnerResult


class CursorRunner(BaseRunner):
    """Stub Cursor runner — not yet implemented."""

    async def run_planning(self, req: Requirement) -> RunnerResult:
        raise NotImplementedError("CursorRunner is not yet implemented")

    async def run_implementation(self, req: Requirement) -> RunnerResult:
        raise NotImplementedError("CursorRunner is not yet implemented")
