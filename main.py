"""Dev Scheduler - File-based AI task scheduler.

Usage:
    python main.py
    # or via entry point:
    dev-scheduler
"""

from src.core.scheduler import run_with_signal_handling


def main() -> None:
    """Entry point for the dev-scheduler."""
    print("Dev Scheduler - AI Task Scheduler")
    print("==================================")
    print("Scanning memory/plan/ for actionable requirements...")
    print("Press Ctrl+C to stop.\n")
    run_with_signal_handling()


if __name__ == "__main__":
    main()
