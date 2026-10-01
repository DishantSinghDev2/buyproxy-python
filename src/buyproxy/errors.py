"""Exceptions raised by the BuyProxy SDK. Everything inherits from :class:`BuyProxyError`."""

from __future__ import annotations

from typing import Any, Optional


class BuyProxyError(Exception):
    """Base class for every error raised by the SDK."""

    def __init__(self, message: str, status: Optional[int] = None, body: Any = None) -> None:
        super().__init__(message)
        self.message = message
        #: HTTP status, or ``None`` when the request never got a response.
        self.status = status
        #: Parsed JSON error body, when the API sent one.
        self.body = body

    def __str__(self) -> str:
        return f"{self.message} (HTTP {self.status})" if self.status else self.message


class ValidationError(BuyProxyError):
    """400 — a parameter was missing or invalid."""


class AuthenticationError(BuyProxyError):
    """401 — the API key is missing or invalid."""


class InsufficientBandwidthError(BuyProxyError):
    """402 — empty reseller pool, or a plan with no GB left."""


class PermissionError_(BuyProxyError):
    """403 — account suspended, key lacks the plan for this endpoint, or the customer is suspended."""


# A friendlier public name that doesn't shadow the builtin ``PermissionError``.
PermissionDeniedError = PermissionError_


class NotFoundError(BuyProxyError):
    """404 — the plan, customer or transaction doesn't exist on this account."""


class RateLimitError(BuyProxyError):
    """429 — more than 60 requests/minute on this key."""

    def __init__(self, message: str, body: Any = None, retry_after_seconds: Optional[float] = None) -> None:
        super().__init__(message, 429, body)
        self.retry_after_seconds = retry_after_seconds


class ServerError(BuyProxyError):
    """5xx — BuyProxy or an upstream provider is unavailable; usually safe to retry."""


class ConnectionError_(BuyProxyError):
    """The request never got a response (DNS, reset, offline)."""


APIConnectionError = ConnectionError_


class TimeoutError_(BuyProxyError):
    """The request exceeded ``timeout``."""


APITimeoutError = TimeoutError_


def error_from_response(status: int, body: Any, retry_after: Optional[float] = None) -> BuyProxyError:
    message = body["error"] if isinstance(body, dict) and isinstance(body.get("error"), str) else f"BuyProxy API error (HTTP {status})"
    if status == 400:
        return ValidationError(message, status, body)
    if status == 401:
        return AuthenticationError(message, status, body)
    if status == 402:
        return InsufficientBandwidthError(message, status, body)
    if status == 403:
        return PermissionDeniedError(message, status, body)
    if status == 404:
        return NotFoundError(message, status, body)
    if status == 429:
        return RateLimitError(message, body, retry_after)
    if status >= 500:
        return ServerError(message, status, body)
    return BuyProxyError(message, status, body)
