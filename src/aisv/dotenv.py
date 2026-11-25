"""A small .env reader.

Supports comments, blank lines, optional `export`, and single or double quotes.
Does not expand variables and does not override keys already set.
"""

from collections.abc import MutableMapping
from pathlib import Path


def parse_env_file(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        values[key] = _unquote(value.strip())
    return values


def load_dotenv(path: Path, environ: MutableMapping[str, str]) -> None:
    if not path.is_file():
        return
    for key, value in parse_env_file(path.read_text(encoding="utf-8")).items():
        environ.setdefault(key, value)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
