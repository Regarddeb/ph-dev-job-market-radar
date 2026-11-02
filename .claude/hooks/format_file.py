"""PostToolUse (Edit|Write): auto-format the edited file. Never blocks.

  .py           -> ruff format + ruff check --fix   (via the scraper uv project)
  .ts/.tsx/...  -> prettier --write + eslint --fix  (dashboard/ only, via local node_modules)

Lint problems that can't be auto-fixed are reported back to Claude (exit 2 on
PostToolUse only shows stderr; the edit has already happened).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import project_dir, read_event, rel_to_project

TS_EXTS = {".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs"}
SKIP_PREFIXES = (
    "dashboard/lib/generated/",
    "dashboard/prisma/migrations/",
    "scraper/tests/fixtures/",
)


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(  # noqa: S603
            cmd, cwd=cwd, capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def format_python(root: Path, path: Path) -> str | None:
    uv = shutil.which("uv")
    if not uv:
        return None
    base = [uv, "run", "--quiet", "--project", str(root / "scraper"), "ruff"]
    run([*base, "format", str(path)], root)
    result = run([*base, "check", "--fix", "--quiet", str(path)], root)
    if result and result.returncode not in (0, None):
        return (result.stdout + result.stderr).strip()
    return None


def format_ts(root: Path, path: Path) -> str | None:
    dash = root / "dashboard"
    node = shutil.which("node")
    prettier = dash / "node_modules" / "prettier" / "bin" / "prettier.cjs"
    eslint = dash / "node_modules" / "eslint" / "bin" / "eslint.js"
    if not node or not prettier.exists():
        return None
    run([node, str(prettier), "--write", "--log-level", "warn", str(path)], dash)
    if eslint.exists():
        result = run([node, str(eslint), "--fix", str(path)], dash)
        if result and result.returncode not in (0, None):
            return (result.stdout + result.stderr).strip()
    return None


def main() -> None:
    event = read_event()
    raw_path = (event.get("tool_input") or {}).get("file_path")
    if not raw_path:
        return
    root = project_dir(event)
    rel = rel_to_project(raw_path, root, event.get("cwd"))
    if rel is None or rel.startswith(SKIP_PREFIXES):
        return
    path = root / rel
    if not path.is_file():
        return

    problems: str | None = None
    if path.suffix == ".py":
        problems = format_python(root, path)
    elif path.suffix in TS_EXTS and rel.startswith("dashboard/"):
        problems = format_ts(root, path)

    if problems:
        print(f"Formatted {rel}; remaining lint issues:\n{problems[:3000]}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
