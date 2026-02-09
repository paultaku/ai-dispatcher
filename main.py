"""Dev Scheduler - AI task scheduler from Notion to Claude Code.

Usage:
    python main.py
    # or via entry point:
    dev-scheduler
"""

from dev_scheduler.scheduler import run_with_signal_handling


def main() -> None:
    """Entry point for the dev-scheduler."""
    print("Dev Scheduler - AI Task Scheduler")
    print("==================================")
    print("Polling Notion for AI-actionable tasks...")
    print("Press Ctrl+C to stop.\n")
    run_with_signal_handling()


if __name__ == "__main__":
    main()
