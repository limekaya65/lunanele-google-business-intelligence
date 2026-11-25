"""Retry transient Google API failures (rate limits, 5xx, network) with backoff.

Permanent errors (bad request, no access, not found) fail fast so they surface
in the run's error list instead of wasting quota.
"""
import random
import time

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
ATTEMPTS = 4


def _status(exc: Exception) -> int | None:
    for getter in (
        lambda e: e.resp.status,               # googleapiclient HttpError
        lambda e: e.response.status_code,      # requests / httpx HTTPError
        lambda e: e.code,                      # google.api_core exceptions
    ):
        try:
            value = getter(exc)
            if isinstance(value, int):
                return value
            if hasattr(value, "value"):          # grpc StatusCode-like
                continue
        except AttributeError:
            continue
    return None


def is_retryable(exc: Exception) -> bool:
    status = _status(exc)
    if status is not None:
        return status in RETRYABLE_STATUS
    # No HTTP status: treat connection/timeouts as transient.
    return isinstance(exc, (ConnectionError, TimeoutError)) or type(exc).__name__ in {
        "ServiceUnavailable", "TooManyRequests", "DeadlineExceeded", "InternalServerError",
        "ConnectTimeout", "ReadTimeout", "ConnectionError", "TransportError",
    }


def with_retry(fn, *args, attempts: int = ATTEMPTS, base_delay: float = 2.0, **kwargs):
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if attempt == attempts or not is_retryable(exc):
                raise
            time.sleep(base_delay * 2 ** (attempt - 1) + random.uniform(0, 1))
