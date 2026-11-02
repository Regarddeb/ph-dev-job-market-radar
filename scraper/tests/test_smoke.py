import importlib

import pytest


@pytest.mark.parametrize("module", ["scraper", "scraper.sources", "scraper.normalize"])
def test_packages_import(module: str) -> None:
    assert importlib.import_module(module) is not None


def test_stdlib_http_not_shadowed() -> None:
    # scraper/http.py must never shadow the stdlib `http` package (httpx depends on it).
    import http

    assert http.__file__ is not None
    assert "scraper" not in http.__file__.replace("\\", "/").split("/")[-2]
