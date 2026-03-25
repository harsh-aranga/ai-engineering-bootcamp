"""
dumper.py — Data artifact persistence.

Dumps data artifacts (JSON, CSV, XML) to a folder structure that mirrors logs/.
Uses run context from logger.py so artifacts correlate with log files.

Usage:
    from common.logger import get_logger
    from common.dumper import dump_json

    logger = get_logger(__file__)
    logger.info("Got embeddings")

    dump_json(embedding_response.model_dump(), "embedding_response")

Creates:
    json/week01_foundations/topic1_tokenization/prg1/2026-03-24/prg1_143022123456_my_message_embedding_response.json
"""

import json
import re
from pathlib import Path
from typing import Any

from common.logger import get_run_context


def _sanitize_label(label: str) -> str:
    """
    Clean label for use in filename.

    - Lowercase
    - Replace spaces and special chars with underscores
    - Collapse multiple underscores
    - Strip leading/trailing underscores

    Args:
        label: raw label string

    Returns:
        Filesystem-safe string
    """
    cleaned = label.lower()
    cleaned = re.sub(r"[^a-z0-9]", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("_")
    return cleaned if cleaned else "unnamed"


def dump_json(data: Any, label: str) -> Path:
    """
    Dump data to a JSON file, correlated with the current log file.

    Args:
        data: any JSON-serializable data (dict, list, etc.)
        label: descriptive label for this dump (e.g., "embedding_response", "token_counts")

    Returns:
        Path to the created JSON file

    Raises:
        RuntimeError: if get_logger() hasn't been called yet
        TypeError: if data is not JSON-serializable

    Example:
        dump_json(response.model_dump(), "openai_response")
    """
    ctx = get_run_context()

    # Build path: json/<relative_dir>/<script_name>/<date>/<script_name>_<time>_<message>_<label>.json
    json_dir = (
        ctx["project_root"]
        / "json"
        / ctx["relative_dir"]
        / ctx["script_name"]
        / ctx["date_str"]
    )
    safe_label = _sanitize_label(label)
    json_filename = f"{ctx['script_name']}_{ctx['time_str']}_{ctx['run_message']}_{safe_label}.json"
    json_path = json_dir / json_filename

    # Create directory structure
    json_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return json_path


if __name__ == "__main__":
    # Sanity check — run from anywhere after pip install -e .
    # python common/dumper.py --run_message="testing dumper"
    from common.logger import get_logger

    logger = get_logger(__file__)
    logger.info("Testing dump_json")

    sample_data = {
        "model": "gpt-4o-mini",
        "tokens": 150,
        "embeddings": [0.1, 0.2, 0.3],
    }

    json_path = dump_json(sample_data, "sample_response")
    logger.info(f"JSON dumped to: {json_path}")
    print(f"\nDumper test complete. Check the json/ directory.")