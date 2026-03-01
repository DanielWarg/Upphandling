"""Tests for scrapers.backoff — retry logic with exponential backoff."""

import httpx
import pytest

from scrapers.backoff import with_backoff, RETRYABLE_STATUS_CODES


def _make_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Create an HTTPStatusError with a given status code."""
    response = httpx.Response(status_code, request=httpx.Request("GET", "https://example.com"))
    return httpx.HTTPStatusError("error", request=response.request, response=response)


class TestWithBackoff:
    def test_success_first_try(self):
        result = with_backoff(lambda: "ok")
        assert result == "ok"

    def test_retry_on_429(self):
        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 3:
                raise _make_status_error(429)
            return "recovered"

        result = with_backoff(fn, max_retries=3, base_delay=0.01)
        assert result == "recovered"
        assert len(calls) == 3

    def test_retry_on_500(self):
        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 2:
                raise _make_status_error(500)
            return "ok"

        result = with_backoff(fn, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert len(calls) == 2

    def test_non_retryable_raises_immediately(self):
        """404 and other non-retryable status codes should raise immediately."""
        calls = []

        def fn():
            calls.append(1)
            raise _make_status_error(404)

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            with_backoff(fn, max_retries=3, base_delay=0.01)
        assert exc_info.value.response.status_code == 404
        assert len(calls) == 1

    def test_max_retries_exhausted(self):
        """Should raise after exhausting all retries."""
        calls = []

        def fn():
            calls.append(1)
            raise _make_status_error(503)

        with pytest.raises(httpx.HTTPStatusError):
            with_backoff(fn, max_retries=2, base_delay=0.01)
        assert len(calls) == 3  # initial + 2 retries

    def test_transport_error_retried(self):
        """Connection errors (TransportError) should be retried."""
        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 2:
                raise httpx.ConnectError("Connection refused")
            return "connected"

        result = with_backoff(fn, max_retries=3, base_delay=0.01)
        assert result == "connected"
        assert len(calls) == 2
