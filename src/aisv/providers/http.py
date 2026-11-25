"""HTTP used by the live providers. Tests substitute their own transport."""

import re
from collections.abc import Mapping

import httpx

_SECRET = re.compile(r"sk-[A-Za-z0-9_\-]{6,}|Bearer\s+\S+", re.IGNORECASE)


class HttpFailure(Exception):
    """The network call failed. The message must not include request headers."""


class HttpxTransport:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, object],
        timeout: float,
    ) -> object:
        try:
            if self._client is None:
                response = httpx.post(
                    url, headers=dict(headers), json=dict(json_body), timeout=timeout
                )
            else:
                response = self._client.post(
                    url, headers=dict(headers), json=dict(json_body), timeout=timeout
                )
        except httpx.TimeoutException as exc:
            raise HttpFailure(f"request timed out after {timeout:g}s") from exc
        except httpx.HTTPError as exc:
            raise HttpFailure(f"request failed: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            detail = _public_body(response.text)
            raise HttpFailure(f"HTTP {response.status_code}: {detail}")
        try:
            payload: object = response.json()
        except ValueError as exc:
            raise HttpFailure("response was not JSON") from exc
        return payload


def _public_body(text: str) -> str:
    flattened = " ".join(text.split())
    redacted = _SECRET.sub("[redacted]", flattened)
    return redacted[:300] if redacted else "no response body"
