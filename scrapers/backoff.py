"""Exponential backoff retry utility for HTTP requests."""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def with_backoff(
    fn: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    """Call *fn* with exponential backoff on retryable HTTP errors.

    Retries on httpx.HTTPStatusError with status 429 or 5xx,
    and on httpx.TransportError (connection errors, timeouts).

    Raises the last exception if all retries are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return fn()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in RETRYABLE_STATUS_CODES:
                raise
            last_exc = exc
        except httpx.TransportError as exc:
            last_exc = exc

        if attempt < max_retries:
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "Attempt %d/%d failed (%s), retrying in %.1fs...",
                attempt + 1, max_retries + 1, last_exc, delay,
            )
            time.sleep(delay)

    raise last_exc  # type: ignore[misc]
