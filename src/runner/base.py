"""Base runner interface for dev-scheduler AI runners."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.core.models import Requirement


@dataclass
class RunnerResult:
    """Result from an AI runner invocation."""

    success: bool
    output: str
    error: str = ""


class BaseRunner(ABC):
    """Abstract base class for AI runners (Claude, Gemini, Cursor, etc.)."""

    @abstractmethod
    async def run_planning(self, req: Requirement) -> RunnerResult:
        """Run the AI planning stage for a requirement."""
        ...

    @abstractmethod
    async def run_implementation(self, req: Requirement) -> RunnerResult:
        """Run the AI implementation stage for a requirement."""
        ...
