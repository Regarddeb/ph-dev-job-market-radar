"""Shared helpers for job-radar Claude Code hooks. Standard library only."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, NoReturn


def read_event() -> dict[str, Any]:
    """Parse the hook event JSON from stdin. Returns {} on bad input."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def project_dir(event: dict[str, Any]) -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    return Path(to_native(raw)).resolve()


def to_native(path: str) -> str:
    """Turn a Git Bash path like /c/Users/x into C:/Users/x on Windows."""
    if os.name == "nt":
        m = re.match(r"^/([a-zA-Z])(/.*)?$", path)
        if m:
            return f"{m.group(1).upper()}:{m.group(2) or '/'}"
    return path


def rel_to_project(path: str, root: Path, cwd: str | None = None) -> str | None:
    """Project-relative POSIX path, or None if the path is outside the project."""
    p = Path(to_native(path))
    if not p.is_absolute():
        p = Path(to_native(cwd)) / p if cwd else root / p
    try:
        rel = p.resolve().relative_to(root)
    except ValueError:
        return None
    return rel.as_posix()


def block(message: str) -> NoReturn:
    """Exit 2: blocks a PreToolUse call; stderr is shown to Claude."""
    print(message, file=sys.stderr)
    sys.exit(2)
