"""Gemini runner stub for dev-scheduler."""

from __future__ import annotations

from src.core.models import Requirement
from src.runner.base import BaseRunner, RunnerResult


class GeminiRunner(BaseRunner):
    """Stub Gemini runner — not yet implemented."""

    async def run_planning(self, req: Requirement) -> RunnerResult:
        raise NotImplementedError("GeminiRunner is not yet implemented")

    async def run_implementation(self, req: Requirement) -> RunnerResult:
        raise NotImplementedError("GeminiRunner is not yet implemented")
