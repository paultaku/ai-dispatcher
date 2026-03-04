"""Run the AI runner once — useful for ad-hoc prompts and manual testing.

Usage:
    # Run from a YAML requirement file (uses status to pick planning vs. implementation):
    python onetime.py memory/plan/myapp/my-feature.yaml

    # Force a specific stage:
    python onetime.py memory/plan/myapp/my-feature.yaml --stage plan
    python onetime.py memory/plan/myapp/my-feature.yaml --stage implement

    # Run with a bare prompt (no YAML needed):
    python onetime.py --prompt "Build a hello world endpoint" --project-path /path/to/project
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import structlog

from src.core.config import Settings
from src.core.models import Requirement, TaskStatus
from src.core.requirement_store import RequirementStore
from src.runner.claude import ClaudeRunner
from src.runner.base import RunnerResult


def _configure_logging(settings: Settings) -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.stdlib.NAME_TO_LEVEL.get(settings.log_level.lower(), 20)
        ),
    )


async def run_once(
    req: Requirement | None,
    prompt: str | None,
    project_path: str,
    stage: str,
    settings: Settings,
) -> RunnerResult:
    """Execute the runner once and return the result."""
    runner = ClaudeRunner(settings)

    if prompt:
        # Bare prompt mode — build a synthetic Requirement
        req = Requirement(
            file_path="",
            app_name="adhoc",
            feature_name="prompt",
            status=TaskStatus.TO_PLAN if stage == "plan" else TaskStatus.READY_TO_IMPLEMENT,
            project_path=project_path,
            describe=prompt,
        )

    if req is None:
        raise ValueError("No requirement or prompt provided")

    if stage == "plan" or (stage == "auto" and req.status == TaskStatus.TO_PLAN):
        print(f"[onetime] Running PLANNING for: {req.feature_name} ({req.app_name})")
        return await runner.run_planning(req)
    else:
        print(f"[onetime] Running IMPLEMENTATION for: {req.feature_name} ({req.app_name})")
        return await runner.run_implementation(req)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the AI runner once with a YAML requirement or a bare prompt."
    )
    parser.add_argument(
        "yaml_file",
        nargs="?",
        help="Path to a YAML requirement file (e.g. memory/plan/myapp/feat.yaml)",
    )
    parser.add_argument(
        "--prompt",
        "-p",
        help="Bare prompt string (used instead of a YAML file)",
    )
    parser.add_argument(
        "--stage",
        choices=["plan", "implement", "auto"],
        default="auto",
        help="Which stage to run. 'auto' uses the YAML status to decide (default: auto)",
    )
    parser.add_argument(
        "--project-path",
        default="",
        help="Working directory for the AI runner (overrides YAML path field)",
    )
    args = parser.parse_args()

    if not args.yaml_file and not args.prompt:
        parser.error("Provide a YAML file path or --prompt")

    settings = Settings()
    _configure_logging(settings)

    req: Requirement | None = None
    project_path = args.project_path

    if args.yaml_file:
        store = RequirementStore()
        yaml_path = Path(args.yaml_file)
        if not yaml_path.exists():
            print(f"Error: file not found: {yaml_path}", file=sys.stderr)
            sys.exit(1)
        req = store._read_yaml(yaml_path)
        if not project_path:
            project_path = req.project_path
        print(f"[onetime] Loaded: {req.app_name}/{req.feature_name} — status={req.status.value}")

    result = asyncio.run(
        run_once(
            req=req,
            prompt=args.prompt,
            project_path=project_path,
            stage=args.stage,
            settings=settings,
        )
    )

    if result.success:
        print("\n[onetime] SUCCESS")
        print("=" * 60)
        print(result.output)
    else:
        print(f"\n[onetime] FAILED: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
