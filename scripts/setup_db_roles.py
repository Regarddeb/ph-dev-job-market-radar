"""Create or rotate the least-privilege Neon roles and rewrite the root .env.

Run it yourself (it prints no secrets):

    uv run --project scraper python scripts/setup_db_roles.py

Reads the owner connection strings that `neon init` / `neon env pull` put in .env:
    DATABASE_URL           owner role, pooled host
    DATABASE_URL_UNPOOLED  owner role, direct host
(or, on re-runs, MIGRATE_DATABASE_URL for the owner/direct URL).

Then:
  - creates jobradar_rw and jobradar_ro with SQL (NOT via the Neon API, so they are not
    members of neon_superuser), setting fresh random passwords on every run
  - grants: rw = SELECT/INSERT/UPDATE/DELETE + sequences, no DDL; ro = SELECT only and
    default_transaction_read_only
  - sets default privileges so tables Prisma Migrate creates later inherit the grants
  - rewrites .env:
        MIGRATE_DATABASE_URL            owner, direct    (Prisma Migrate)
        DATABASE_URL                    jobradar_rw, pooled  (scraper)
        JOBRADAR_READONLY_DATABASE_URL  jobradar_ro, pooled  (dashboard, postgres MCP)
    and drops DATABASE_URL_UNPOOLED (its value moves to MIGRATE_DATABASE_URL).

Re-running rotates both passwords: update GitHub/Vercel secrets afterwards.
Note: `neon env pull` overwrites DATABASE_URL with the owner role; re-run this script after it.
"""

from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
RW, RO = "jobradar_rw", "jobradar_ro"
DEFAULTS = "ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public"
KEY_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def read_env(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        m = KEY_RE.match(line)
        if m:
            values[m.group(1)] = m.group(2).strip().strip("'\"")
    return lines, values


def write_env(path: Path, lines: list[str], updates: dict[str, str | None]) -> None:
    """Replace keys in place, drop keys mapped to None, append new keys at the end."""
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        m = KEY_RE.match(line)
        if m and m.group(1) in updates:
            key = m.group(1)
            if key in seen or updates[key] is None:
                continue
            out.append(f'{key}="{updates[key]}"')
            seen.add(key)
        else:
            out.append(line)
    new = [k for k, v in updates.items() if k not in seen and v is not None]
    if new:
        out += ["", "# Least-privilege roles (scripts/setup_db_roles.py)"]
        out += [f'{k}="{updates[k]}"' for k in new]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def with_credentials(url: str, user: str, password: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}{port}"
    return urlunsplit(parts._replace(netloc=netloc))


def is_pooled(url: str) -> bool:
    return "-pooler." in (urlsplit(url).hostname or "")


def main() -> int:
    if not ENV_PATH.exists():
        print(
            "No .env at repo root. Run `neon init` or `neon env pull` first.",
            file=sys.stderr,
        )
        return 1
    lines, env = read_env(ENV_PATH)

    owner_direct = env.get("DATABASE_URL_UNPOOLED") or env.get("MIGRATE_DATABASE_URL")
    if not owner_direct or is_pooled(owner_direct):
        print(
            "Need the owner's direct URL in DATABASE_URL_UNPOOLED or MIGRATE_DATABASE_URL.",
            file=sys.stderr,
        )
        return 1
    owner = urlsplit(owner_direct).username
    dbname = urlsplit(owner_direct).path.lstrip("/")

    # Pooled host = direct endpoint host with "-pooler" after the endpoint id.
    direct_host = urlsplit(owner_direct).hostname or ""
    endpoint, _, rest = direct_host.partition(".")
    pooled_base = urlunsplit(
        urlsplit(owner_direct)._replace(netloc=f"x@{endpoint}-pooler.{rest}")
    )

    passwords = {RW: secrets.token_urlsafe(32), RO: secrets.token_urlsafe(32)}
    ident = sql.Identifier

    with psycopg.connect(owner_direct, autocommit=True) as conn:
        for role, pw in passwords.items():
            exists = conn.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)
            ).fetchone()
            verb = "ALTER" if exists else "CREATE"
            conn.execute(
                sql.SQL(
                    "{} ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
                ).format(sql.SQL(verb), ident(role), sql.Literal(pw))
            )
            print(f"{verb.lower()}d role {role}")

        stmts = [
            # Database + schema access
            "GRANT CONNECT ON DATABASE {db} TO {rw}, {ro}",
            "GRANT USAGE ON SCHEMA public TO {rw}, {ro}",
            "REVOKE CREATE ON SCHEMA public FROM PUBLIC, {rw}, {ro}",
            # Existing objects
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {rw}",
            "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {rw}",
            "GRANT SELECT ON ALL TABLES IN SCHEMA public TO {ro}",
            # Future objects created by the owner (Prisma Migrate)
            f"{DEFAULTS} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {{rw}}",
            f"{DEFAULTS} GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {{rw}}",
            f"{DEFAULTS} GRANT SELECT ON TABLES TO {{ro}}",
            # Belt and braces for the read-only role
            "ALTER ROLE {ro} SET default_transaction_read_only = on",
            "ALTER ROLE {ro} SET statement_timeout = '30s'",
            "ALTER ROLE {rw} SET statement_timeout = '5min'",
        ]
        names = {
            "db": ident(dbname),
            "rw": ident(RW),
            "ro": ident(RO),
            "owner": ident(owner),
        }
        for stmt in stmts:
            conn.execute(sql.SQL(stmt).format(**names))
        print("grants and default privileges applied")

    # Verify each role can log in through the pooler, and that ro can't write.
    rw_url = with_credentials(pooled_base, RW, passwords[RW])
    ro_url = with_credentials(pooled_base, RO, passwords[RO])
    with psycopg.connect(rw_url) as c:
        c.execute("SELECT 1")
    with psycopg.connect(ro_url) as c:
        ro_flag = c.execute("SHOW default_transaction_read_only").fetchone()
        try:
            c.execute("CREATE TEMP TABLE _ro_probe (x int)")
            ro_blocked = False
        except psycopg.Error:
            ro_blocked = True
    print(
        f"login ok: {RW}, {RO} (read_only={ro_flag[0] if ro_flag else '?'}, "
        f"write blocked={ro_blocked})"
    )

    write_env(
        ENV_PATH,
        lines,
        {
            "MIGRATE_DATABASE_URL": owner_direct,
            "DATABASE_URL": rw_url,
            "JOBRADAR_READONLY_DATABASE_URL": ro_url,
            "DATABASE_URL_UNPOOLED": None,
        },
    )
    print(
        ".env updated: MIGRATE_DATABASE_URL, DATABASE_URL, JOBRADAR_READONLY_DATABASE_URL"
    )
    print(f"database: {dbname}; owner: {owner}. Passwords were not printed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
