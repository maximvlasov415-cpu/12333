"""Чтение и правка значений в .env. Используется скриптами деплоя.

    python3 envtool.py get KEY [FILE]
    python3 envtool.py set KEY VALUE [FILE]
"""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_FILE = "/opt/pavlik/.env"


def _is_key(line: str, key: str) -> bool:
    return not line.lstrip().startswith("#") and line.split("=", 1)[0].strip() == key


def get(path: Path, key: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if _is_key(line, key):
            return line.split("=", 1)[1].strip()
    return ""


def put(path: Path, key: str, value: str) -> None:
    lines, done = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if _is_key(line, key):
            lines.append(f"{key}={value}")
            done = True
        else:
            lines.append(line)
    if not done:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    match argv:
        case ["get", key, *rest]:
            print(get(Path(rest[0] if rest else DEFAULT_FILE), key))
        case ["set", key, value, *rest]:
            put(Path(rest[0] if rest else DEFAULT_FILE), key, value)
        case _:
            print(__doc__, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
