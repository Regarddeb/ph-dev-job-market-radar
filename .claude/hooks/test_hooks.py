"""Self-test for the guard hooks. Run from the repo root:

uv run --no-project python .claude/hooks/test_hooks.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
ROOT = HOOKS.parent.parent
# Assembled so this file's own text doesn't contain the forbidden domains.
FORBIDDEN_DOMAINS = ["linked" + "in.com", "online" + "jobs.ph", "ph.job" + "street.com"]


def run(hook: str, event: dict) -> int:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT)}
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOKS / hook)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result.returncode


def edit(path: Path | str) -> dict:
    return {
        "tool_name": "Write",
        "cwd": str(ROOT),
        "tool_input": {"file_path": str(path)},
    }


def bash(command: str) -> dict:
    return {"tool_name": "Bash", "cwd": str(ROOT), "tool_input": {"command": command}}


CASES: list[tuple[str, str, dict, int]] = [
    (".env blocked", "guard_files.py", edit(ROOT / ".env"), 2),
    (
        "dashboard/.env.local blocked",
        "guard_files.py",
        edit(ROOT / "dashboard/.env.local"),
        2,
    ),
    (".env.example allowed", "guard_files.py", edit(ROOT / ".env.example"), 0),
    (
        "existing fixture blocked",
        "guard_files.py",
        edit(ROOT / "scraper/tests/fixtures/.gitkeep"),
        2,
    ),
    (
        "new fixture allowed",
        "guard_files.py",
        edit(ROOT / "scraper/tests/fixtures/new-fixture.json"),
        0,
    ),
    (
        "untracked migration allowed",
        "guard_files.py",
        edit(ROOT / "dashboard/prisma/migrations/0_new/migration.sql"),
        0,
    ),
    ("relative .env blocked", "guard_files.py", edit(".env"), 2),
    ("normal source allowed", "guard_files.py", edit(ROOT / "scraper/pipeline.py"), 0),
    *[
        (f"bash {d} blocked", "guard_bash.py", bash(f"curl -s https://www.{d}/jobs"), 2)
        for d in FORBIDDEN_DOMAINS
    ],
    (
        "prose 'indeed.' allowed",
        "guard_bash.py",
        bash('git commit -m "works, indeed."'),
        0,
    ),
    (
        "allowed source allowed",
        "guard_bash.py",
        bash("curl https://remotive.com/api/remote-jobs"),
        0,
    ),
]


def main() -> int:
    failures = 0
    for name, hook, event, expected in CASES:
        got = run(hook, event)
        ok = got == expected
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}  (exit {got}, expected {expected})")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
