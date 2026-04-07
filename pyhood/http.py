"""HTTP layer — session management, rate limiting, retries."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import requests

from pyhood.exceptions import APIError, RateLimitError

logger = logging.getLogger("pyhood")

# Defaults
DEFAULT_TIMEOUT = 16  # seconds
MAX_RETRIES = 2
RATE_LIMIT_DELAY = 0.02  # seconds between requests
ALLOWED_HOST_SUFFIX = ".robinhood.com"
ALLOWED_HOST = "robinhood.com"


class Session:
    """Managed HTTP session with rate limiting and retries."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "*/*",
            "Accept-Encoding": "gzip,deflate,br",
            "Accept-Language": "en-US,en;q=1",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "X-Robinhood-API-Version": "1.431.4",
            "Connection": "keep-alive",
            "User-Agent": "*",
        })
        self._timeout = timeout
        self._last_request_at: float = 0.0

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._session.headers)

    def set_auth(self, token_type: str, access_token: str) -> None:
        """Set the authorization header."""
        self._session.headers["Authorization"] = f"{token_type} {access_token}"

    def clear_auth(self) -> None:
        """Remove the authorization header."""
        self._session.headers.pop("Authorization", None)

    @property
    def is_authenticated(self) -> bool:
        return "Authorization" in self._session.headers

    def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)

    def _request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
        json_data: dict | None = None,
        timeout: float | None = None,
        accept_codes: tuple[int, ...] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with rate limiting and retries."""
        self._validate_request_url(url)
        self._rate_limit()

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                self._last_request_at = time.monotonic()
                # Temporarily switch to JSON content type if sending json_data
                if json_data:
                    self._session.headers["Content-Type"] = "application/json"
                resp = self._session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json_data,
                    timeout=timeout or self._timeout,
                )
                if json_data:
                    self._session.headers["Content-Type"] = (
                        "application/x-www-form-urlencoded; charset=utf-8"
                    )

                # Rate limited
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", "5"))
                    if attempt < MAX_RETRIES:
                        logger.warning(f"Rate limited, retrying in {retry_after}s")
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError(retry_after=retry_after)

                # Some endpoints (login) return 400/403 with valid JSON data
                if accept_codes and resp.status_code in accept_codes:
                    if resp.text:
                        return resp.json()
                    return {}

                # Auth errors — don't retry
                if resp.status_code in (401, 403):
                    raise APIError(
                        f"Auth error: {resp.status_code}",
                        status_code=resp.status_code,
                        response=resp.json() if resp.text else None,
                    )

                resp.raise_for_status()

                if not resp.text:
                    return {}
                return resp.json()

            except (requests.ConnectionError, requests.Timeout, ConnectionError) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    wait = (attempt + 1) * 2
                    logger.warning(f"Request failed ({e}), retrying in {wait}s")
                    time.sleep(wait)
                    continue
                raise APIError(f"Request failed after {MAX_RETRIES + 1} attempts: {e}") from e

        raise APIError(f"Request failed: {last_error}") from last_error

    def get(self, url: str, params: dict | None = None, **kwargs: Any) -> dict[str, Any]:
        return self._request("GET", url, params=params, **kwargs)

    def post(
        self,
        url: str,
        data: dict | None = None,
        accept_codes: tuple[int, ...] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._request("POST", url, data=data, accept_codes=accept_codes, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> dict[str, Any]:
        return self._request("DELETE", url, **kwargs)

    def get_paginated(self, url: str, params: dict | None = None) -> list[dict[str, Any]]:
        """Follow Robinhood's pagination to collect all results."""
        results: list[dict[str, Any]] = []
        while url:
            data = self.get(url, params=params)
            params = None  # Only pass params on the first request
            if isinstance(data, dict):
                results.extend(data.get("results", []))
                next_url = data.get("next")
                if next_url:
                    self._validate_request_url(next_url)
                url = next_url
            else:
                break
        return results

    @staticmethod
    def _is_allowed_host(hostname: str | None) -> bool:
        """Allow only robinhood.com and its subdomains."""
        if not hostname:
            return False
        host = hostname.lower().rstrip(".")
        return host == ALLOWED_HOST or host.endswith(ALLOWED_HOST_SUFFIX)

    def _validate_request_url(self, url: str) -> None:
        """Reject non-HTTPS and non-robinhood destinations."""
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise APIError(f"Blocked non-HTTPS request URL: {url}")
        if not self._is_allowed_host(parsed.hostname):
            raise APIError(f"Blocked request to non-whitelisted host: {url}")
