"""Tests for the shared HTTP client, using httpx.MockTransport (never the network)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from scraper.http import FetchError, HttpClient, UserAgentMissingError, parse_retry_after

UA = "job-radar-test/0.1 (+https://example.invalid)"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(handler, clock: FakeClock | None = None, **kw) -> HttpClient:
    clock = clock or FakeClock()
    return HttpClient(
        UA,
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        **kw,
    )


def test_requires_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCRAPER_USER_AGENT", raising=False)
    with pytest.raises(UserAgentMissingError):
        HttpClient()
    with pytest.raises(UserAgentMissingError):
        HttpClient("   ")


def test_sends_identifying_user_agent() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["User-Agent"])
        return httpx.Response(200, text="ok")

    with make_client(handler) as client:
        assert client.get("https://example.invalid/a").text == "ok"
    assert seen == [UA]


def test_rate_limits_per_host() -> None:
    clock = FakeClock()
    with make_client(lambda r: httpx.Response(200), clock, min_interval_s=2.0) as client:
        client.get("https://a.invalid/1")
        client.get("https://a.invalid/2")  # same host: must wait 2 s
        client.get("https://b.invalid/1")  # other host: no wait
    assert clock.sleeps == [2.0]


def test_host_specific_interval() -> None:
    clock = FakeClock()
    with make_client(
        lambda r: httpx.Response(200), clock, host_intervals={"slow.invalid": 30.0}
    ) as client:
        client.get("https://slow.invalid/1")
        client.get("https://slow.invalid/2")
    assert clock.sleeps == [30.0]


def test_retries_5xx_then_succeeds() -> None:
    statuses = iter([503, 502, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses))

    clock = FakeClock()
    with make_client(handler, clock, min_interval_s=0) as client:
        assert client.get("https://x.invalid/").status_code == 200
        assert client.requests_made == 3
    assert len(clock.sleeps) == 2
    assert 2.0 <= clock.sleeps[0] <= 3.0  # base backoff + jitter
    assert 4.0 <= clock.sleeps[1] <= 5.0


def test_honors_retry_after_seconds() -> None:
    responses = iter([httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200)])
    clock = FakeClock()
    with make_client(lambda r: next(responses), clock, min_interval_s=0) as client:
        client.get("https://x.invalid/")
    assert clock.sleeps == [7.0]


def test_caps_huge_retry_after() -> None:
    responses = iter([httpx.Response(429, headers={"Retry-After": "86400"}), httpx.Response(200)])
    clock = FakeClock()
    with make_client(lambda r: next(responses), clock, min_interval_s=0) as client:
        client.get("https://x.invalid/")
    assert clock.sleeps == [300.0]


def test_gives_up_after_max_attempts() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    with make_client(handler, min_interval_s=0) as client, pytest.raises(FetchError):
        client.get("https://x.invalid/")
    assert calls == 3


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410])
def test_does_not_retry_other_4xx(status: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    with make_client(handler) as client, pytest.raises(FetchError) as info:
        client.get("https://x.invalid/")
    assert calls == 1
    assert info.value.status == status


def test_retries_network_errors() -> None:
    attempts = iter([httpx.ConnectError("boom"), None])

    def handler(request: httpx.Request) -> httpx.Response:
        exc = next(attempts)
        if exc:
            raise exc
        return httpx.Response(200)

    with make_client(handler, min_interval_s=0) as client:
        assert client.get("https://x.invalid/").status_code == 200


def test_parse_retry_after_http_date() -> None:
    now = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)
    assert parse_retry_after("Fri, 06 Nov 2026 12:00:30 GMT", now=now) == 30.0
    assert parse_retry_after("Fri, 06 Nov 2026 11:00:00 GMT", now=now) == 0.0
    assert parse_retry_after("garbage", now=now) is None
    assert parse_retry_after(None) is None
