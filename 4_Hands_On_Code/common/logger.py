"""
logger.py — Structured logging with automatic path generation.

Creates log files that mirror the source directory structure:
    logs/week01_foundations/topic1_tokenization/prg1/2026-03-24/prg1_my_message_143022123456.log

Features:
    - Auto-captures --run_message from CLI (no boilerplate in scripts)
    - Builds log path from caller's __file__
    - Writes to file AND console simultaneously
    - All log levels captured (DEBUG and up)

Usage:
    from common.logger import get_logger

    logger = get_logger(__file__)
    logger.info("Starting experiment")

    # Run as: python prg1.py --run_message="testing chunking"
"""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path


def _find_project_root() -> Path:
    """
    Walk up from this file's location until we find pyproject.toml.
    That's the project root (4_Hands_On_Code/).

    Returns:
        Path to project root directory

    Raises:
        FileNotFoundError: if pyproject.toml cannot be found
    """
    current = Path(__file__).resolve().parent
    while True:
        if (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            raise FileNotFoundError(
                "Could not find pyproject.toml. "
                "Expected it at the root of 4_Hands_On_Code/."
            )
        current = parent


def _extract_run_message() -> str:
    """
    Parse sys.argv for --run_message flag.

    Supports:
        --run_message="my message here"
        --run_message "my message here"

    Returns:
        Sanitized message string, or "default_run" if not provided
    """
    message = "default_run"

    for i, arg in enumerate(sys.argv):
        # Handle --run_message="value" format
        if arg.startswith("--run_message="):
            message = arg.split("=", 1)[1]
            break
        # Handle --run_message "value" format
        if arg == "--run_message" and i + 1 < len(sys.argv):
            message = sys.argv[i + 1]
            break

    return _sanitize_message(message)


def _sanitize_message(message: str) -> str:
    """
    Clean message for use in filename.

    - Lowercase
    - Replace spaces and special chars with underscores
    - Collapse multiple underscores
    - Strip leading/trailing underscores

    Args:
        message: raw message string from CLI

    Returns:
        Filesystem-safe string
    """
    # Lowercase
    cleaned = message.lower()
    # Replace non-alphanumeric with underscore
    cleaned = re.sub(r"[^a-z0-9]", "_", cleaned)
    # Collapse multiple underscores
    cleaned = re.sub(r"_+", "_", cleaned)
    # Strip leading/trailing underscores
    cleaned = cleaned.strip("_")

    return cleaned if cleaned else "default_run"


def _build_log_path(caller_file: str) -> Path:
    """
    Build the full log file path from caller's __file__.

    Example:
        caller_file: /path/to/4_Hands_On_Code/week01_foundations/topic1_tokenization/prg1.py
        returns: /path/to/4_Hands_On_Code/logs/week01_foundations/topic1_tokenization/prg1/2026-03-24/prg1_my_message_143022123456.log

    Args:
        caller_file: the __file__ of the script requesting a logger

    Returns:
        Full path to the log file
    """
    project_root = _find_project_root()
    caller_path = Path(caller_file).resolve()

    # Get the script name without extension
    script_name = caller_path.stem

    # Get relative path from project root to caller's directory
    try:
        relative_dir = caller_path.parent.relative_to(project_root)
    except ValueError:
        # Caller is outside project root — use just the script name
        relative_dir = Path(script_name)

    # Build components
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S") + f"{now.microsecond:06d}"
    run_message = _extract_run_message()

    # Construct: logs/<relative_dir>/<script_name>/<date>/<script_name>_<message>_<time>.log
    log_dir = project_root / "logs" / relative_dir / script_name / date_str
    log_filename = f"{script_name}_{time_str}_{run_message}.log"

    return log_dir / log_filename


def get_logger(caller_file: str) -> logging.Logger:
    """
    Create and configure a logger for the calling script.

    - Creates log directory structure if it doesn't exist
    - Writes to file (all levels) AND console (all levels)
    - Auto-captures --run_message from CLI for filename

    Args:
        caller_file: pass __file__ from your script

    Returns:
        Configured logging.Logger instance

    Example:
        from common.logger import get_logger

        logger = get_logger(__file__)
        logger.info("Experiment started")
    """
    log_path = _build_log_path(caller_file)

    # Create directory structure
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a unique logger name based on log path to avoid collisions
    logger_name = str(log_path)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding handlers multiple times if get_logger is called again
    if logger.handlers:
        return logger

    # Formatter — same for file and console
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler — captures everything
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler — also captures everything
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Log the file location at startup for easy reference
    logger.debug(f"Log file: {log_path}")

    return logger


if __name__ == "__main__":
    # Sanity check — run from anywhere after pip install -e .
    # python common/logger.py --run_message="testing logger setup"
    logger = get_logger(__file__)
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    print(f"\nLogger test complete. Check the logs/ directory.")