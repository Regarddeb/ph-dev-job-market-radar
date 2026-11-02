"""PreToolUse (Edit|Write|NotebookEdit): block edits to protected files.

Blocked:
  - .env* files, except .env.example (secrets never pass through Claude)
  - existing files in scraper/tests/fixtures/ (fixtures are immutable; add a new one)
  - git-tracked files in dashboard/prisma/migrations/ (never edit a committed migration)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import block, project_dir, read_event, rel_to_project

FIXTURES = "scraper/tests/fixtures/"
MIGRATIONS = "dashboard/prisma/migrations/"


def is_git_tracked(root: Path, rel: str) -> bool:
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "ls-files", "--error-unmatch", "--", rel],  # noqa: S607
            cwd=root,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        # Can't tell: fail closed for migrations.
        return True
    return result.returncode == 0


def main() -> None:
    event = read_event()
    tool_input = event.get("tool_input") or {}
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw_path:
        return

    name = PurePosixPath(raw_path.replace("\\", "/")).name
    if name.startswith(".env") and name != ".env.example":
        block(
            f"Blocked: {name} holds secrets and must not be edited by Claude. "
            "Update .env.example instead and ask the user to change their .env by hand."
        )

    root = project_dir(event)
    rel = rel_to_project(raw_path, root, event.get("cwd"))
    if rel is None:
        return

    if rel.startswith(FIXTURES) and (root / rel).exists():
        block(
            f"Blocked: {rel} is an existing test fixture, and fixtures are immutable. "
            "Save a new fixture file (e.g. with a date suffix) and point a new test at it."
        )

    if rel.startswith(MIGRATIONS) and is_git_tracked(root, rel):
        block(
            f"Blocked: {rel} is a committed Prisma migration. Never edit it; change "
            "dashboard/prisma/schema.prisma and run `pnpm prisma migrate dev --name <change>`."
        )


if __name__ == "__main__":
    main()
