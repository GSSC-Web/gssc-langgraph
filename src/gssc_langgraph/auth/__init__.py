"""Agent Server API-key / Bearer auth for the LangGraph CLI server.

Wire via ``langgraph.json`` → ``auth.path`` = ``./src/gssc_langgraph/auth/__init__.py:auth``.

Behaviour:
- If ``GSSC_LANGGRAPH_API_KEY`` is unset/empty (or ``GSSC_LANGGRAPH_AUTH_BYPASS``
  is truthy), requests are allowed (local/dev bypass).
- Otherwise require ``Authorization: Bearer <key>`` (or ``x-api-key``) matching
  the configured key (comma-separated keys supported for rotation).
- ``GET /ok`` stays reachable without credentials for process probes.

Cloudflare Access (edge SSO / service tokens) is separate: it may sit in
front of a deployment but does not replace this app-level API key.

Note: Python ``Auth.authenticate`` receives named params (``authorization``,
``headers``, ``path``, ``method``, …) — not a Request object like the TS SDK.
Headers may use ``bytes`` or ``str`` keys depending on the runtime.
"""

from __future__ import annotations

import hmac
import os
from typing import Any, Mapping, TypedDict

from langgraph_sdk import Auth
from langgraph_sdk.auth.exceptions import HTTPException

API_KEY_ENV = "GSSC_LANGGRAPH_API_KEY"
AUTH_BYPASS_ENV = "GSSC_LANGGRAPH_AUTH_BYPASS"

_UNAUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


class AuthIdentity(TypedDict):
    identity: str
    permissions: list[str]
    is_authenticated: bool
    display_name: str


def _truthy_env(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in ("1", "true", "yes", "on")


def configured_api_keys(env: Mapping[str, str] | None = None) -> list[str]:
    """Configured API keys from env (empty → local bypass when bypass not forced)."""
    source = env if env is not None else os.environ
    raw = (source.get(API_KEY_ENV) or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def is_auth_bypass_enabled(env: Mapping[str, str] | None = None) -> bool:
    """True when auth should allow requests without a matching API key."""
    source = env if env is not None else os.environ
    if _truthy_env(source.get(AUTH_BYPASS_ENV)):
        return True
    return len(configured_api_keys(source)) == 0


def _decode_header_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _header_get(headers: Mapping[Any, Any] | None, name: str) -> str | None:
    if not headers:
        return None
    want = name.lower().encode("ascii")
    want_str = name.lower()
    for key, value in headers.items():
        if isinstance(key, bytes):
            if key.lower() == want:
                text = _decode_header_value(value).strip()
                return text or None
        else:
            if str(key).lower() == want_str:
                text = _decode_header_value(value).strip()
                return text or None
    return None


def extract_api_key(
    *,
    authorization: str | None = None,
    headers: Mapping[Any, Any] | None = None,
) -> str | None:
    """Extract Bearer token or x-api-key from auth params / headers."""
    auth_header = authorization
    if auth_header is None:
        auth_header = _header_get(headers, "authorization")
    if auth_header:
        parts = auth_header.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()

    x_api_key = _header_get(headers, "x-api-key")
    return x_api_key if x_api_key else None


def api_key_matches(provided: str, keys: list[str] | tuple[str, ...]) -> bool:
    """Timing-safe compare against configured keys."""
    provided_b = provided.encode("utf-8")
    for key in keys:
        expected = key.encode("utf-8")
        if len(provided_b) == len(expected) and hmac.compare_digest(
            provided_b, expected
        ):
            return True
    return False


def authenticate_request(
    *,
    path: str | None = None,
    method: str | None = None,  # noqa: ARG001 — accepted for Auth signature parity
    authorization: str | None = None,
    headers: Mapping[Any, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> AuthIdentity:
    """Pure authenticate helper (unit-testable).

    Raises :class:`HTTPException` on missing/invalid credentials when auth is
    enforced.
    """
    # Process liveness — keep probeable without a key even when auth is on.
    pathname = (path or "").split("?", 1)[0]
    if pathname == "/ok":
        return {
            "identity": "healthcheck",
            "permissions": [],
            "is_authenticated": True,
            "display_name": "healthcheck",
        }

    source = env if env is not None else os.environ
    if is_auth_bypass_enabled(source):
        return {
            "identity": "local-bypass",
            "permissions": [],
            "is_authenticated": True,
            "display_name": "local-bypass",
        }

    token = extract_api_key(authorization=authorization, headers=headers)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization Bearer token (or x-api-key)",
            headers=dict(_UNAUTH_HEADERS),
        )

    keys = configured_api_keys(source)
    if not api_key_matches(token, keys):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers=dict(_UNAUTH_HEADERS),
        )

    return {
        "identity": "api-key",
        "permissions": [],
        "is_authenticated": True,
        "display_name": "api-key",
    }


auth = Auth()


@auth.authenticate
async def _authenticate(
    path: str,
    headers: dict,  # bytes or str keys depending on runtime
    authorization: str | None = None,
    method: str | None = None,
) -> AuthIdentity:
    return authenticate_request(
        path=path,
        method=method,
        authorization=authorization,
        headers=headers,
    )


__all__ = [
    "API_KEY_ENV",
    "AUTH_BYPASS_ENV",
    "AuthIdentity",
    "api_key_matches",
    "auth",
    "authenticate_request",
    "configured_api_keys",
    "extract_api_key",
    "is_auth_bypass_enabled",
]
