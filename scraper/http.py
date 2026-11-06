"""The one shared HTTP client for every source adapter.

Rules it enforces (see .claude/skills/scraping-etiquette):
  - identifying User-Agent from SCRAPER_USER_AGENT (fails fast if unset)
  - per-host minimum interval between requests (default 1 s, overridable per host)
  - retries only on 429, 5xx and network errors: max 3 attempts, exponential backoff
    with jitter, honoring Retry-After (seconds or HTTP-date, capped)
  - connect/read timeouts; no cookies are persisted between runs
Never call httpx directly from an adapter.
"""

from __future__ import annotations

import email.utils
import logging
import os
import random
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from types import TracebackType
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
MAX_RETRY_AFTER_S = 300.0


class UserAgentMissingError(RuntimeError):
    pass


class FetchError(RuntimeError):
    """A request failed after all retries, or with a non-retryable status."""

    def __init__(self, message: str, *, status: int | None = None, url: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.url = url


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    """Seconds to wait from a Retry-After header (delta-seconds or HTTP-date)."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - (now or datetime.now(UTC))).total_seconds())


class HttpClient:
    """Polite, rate-limited, retrying wrapper around one httpx.Client."""

    def __init__(
        self,
        user_agent: str | None = None,
        *,
        min_interval_s: float = 1.0,
        host_intervals: Mapping[str, float] | None = None,
        max_attempts: int = 3,
        backoff_base_s: float = 2.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        ua = user_agent if user_agent is not None else os.environ.get("SCRAPER_USER_AGENT", "")
        if not ua.strip():
            raise UserAgentMissingError(
                "SCRAPER_USER_AGENT is not set; every request must identify the project."
            )
        self.min_interval_s = min_interval_s
        self.host_intervals = dict(host_intervals or {})
        self.max_attempts = max_attempts
        self.backoff_base_s = backoff_base_s
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request: dict[str, float] = {}
        self.requests_made = 0
        self._client = httpx.Client(
            headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"},
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
            transport=transport,
        )

    # -- context manager -------------------------------------------------------------
    def __enter__(self) -> HttpClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- internals -------------------------------------------------------------------
    def _wait_for_host(self, host: str) -> None:
        interval = self.host_intervals.get(host, self.min_interval_s)
        last = self._last_request.get(host)
        if last is not None:
            remaining = interval - (self._monotonic() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request[host] = self._monotonic()

    def _backoff(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(retry_after, MAX_RETRY_AFTER_S)
        return self.backoff_base_s * (2 ** (attempt - 1)) + random.uniform(0, 1)  # noqa: S311

    # -- public ----------------------------------------------------------------------
    def get(self, url: str, *, params: Mapping[str, str] | None = None) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            self._wait_for_host(host)
            self.requests_made += 1
            try:
                response = self._client.get(url, params=params)
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                retry_after = None
            else:
                if response.status_code < 400:
                    return response
                if response.status_code not in RETRY_STATUSES:
                    raise FetchError(
                        f"GET {url} -> HTTP {response.status_code}",
                        status=response.status_code,
                        url=url,
                    )
                last_error = f"HTTP {response.status_code}"
                retry_after = parse_retry_after(response.headers.get("Retry-After"))
            if attempt < self.max_attempts:
                delay = self._backoff(attempt, retry_after)
                log.warning(
                    "GET %s failed (%s); retry %d in %.1fs", url, last_error, attempt, delay
                )
                self._sleep(delay)
        raise FetchError(
            f"GET {url} failed after {self.max_attempts} attempts: {last_error}", url=url
        )
