"""
config.py — .env loader.

Reads the .env file from the project root and returns its contents as a plain dict.
Keys are returned exactly as written in .env — no renaming, no reshaping.

Does NOT mutate os.environ. No global side effects.
Caller is responsible for passing values to whatever needs them.

For hardcoded values that never change, see constants.py.
"""

from pathlib import Path
from dotenv import dotenv_values


class Config:
    """
    Thin wrapper around the .env dict.
    Raises KeyError immediately if a requested key is missing —
    instead of returning None and failing silently downstream.
    """

    def __init__(self, values: dict) -> None:
        """
        Args:
            values: raw key-value pairs loaded from .env
        """
        self._values = values

    def get(self, key: str) -> str:
        """
        Fetch a value by its exact .env key name.

        Args:
            key: the key name as written in .env e.g. "OPEN_AI_KEY"

        Returns:
            the value as a string

        Raises:
            KeyError: if the key is not present or empty in .env
        """
        if key not in self._values or not self._values[key]:
            raise KeyError(
                f"Key '{key}' not found in .env. "
                f"Available keys: {list(self._values.keys())}"
            )
        return self._values[key]


def _find_dotenv() -> Path:
    """
    Walk up from this file's location until a .env file is found.
    Works regardless of where the calling script lives.

    Raises:
        FileNotFoundError: if no .env is found up to filesystem root
    """
    current = Path(__file__).resolve().parent
    while True:
        candidate = current / ".env"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            raise FileNotFoundError(
                "Could not find a .env file. "
                "Expected it at the root of 4_Hands_On_Code/."
            )
        current = parent


def get_config() -> Config:
    """
    Load .env from project root and return a Config instance.

    Returns:
        Config: wrapper around raw .env key-value pairs

    Raises:
        FileNotFoundError: if .env cannot be found
    """
    dotenv_path = _find_dotenv()
    values = dotenv_values(dotenv_path)
    return Config(values)


if __name__ == "__main__":
    # Sanity check — run from anywhere after pip install -e .
    # python common/config.py
    config = get_config()
    key = config.get("OPEN_AI_KEY")
    print(f"Config loaded OK. OPEN_AI_KEY starts with: {key[:8]}...")