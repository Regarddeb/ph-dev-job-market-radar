"""PreToolUse (Bash|PowerShell): block commands that reference forbidden job sites.

These sites prohibit scraping (see docs/SOURCES.md). Matching is on domain-like
text, so ordinary words ("indeed.") in prose don't trip it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import block, read_event

FORBIDDEN = re.compile(
    r"""
    \b(
        jobstreet\.[a-z]
      | jobsdb\.[a-z]
      | seek\.com
      | linkedin\.com
      | remotive\.com
      | indeed\.[a-z]
      | upwork\.com
      | onlinejobs\.ph
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def main() -> None:
    event = read_event()
    command = (event.get("tool_input") or {}).get("command") or ""
    match = FORBIDDEN.search(command)
    if match:
        block(
            f"Blocked: command references a forbidden source ({match.group(1)}...). "
            "JobStreet, JobsDB/SEEK, LinkedIn, Indeed, Upwork, OnlineJobs.ph and Remotive must "
            "never be fetched or scraped. Only use sources marked Allowed in docs/SOURCES.md. "
            "(This also fires on prose that names these domains; use the Edit tool for docs.)"
        )


if __name__ == "__main__":
    main()
