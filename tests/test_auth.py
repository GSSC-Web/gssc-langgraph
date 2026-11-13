"""API-key / Bearer auth helpers."""

from __future__ import annotations

import pytest
from langgraph_sdk.auth.exceptions import HTTPException

from gssc_langgraph.auth import (
    API_KEY_ENV,
    AUTH_BYPASS_ENV,
    api_key_matches,
    authenticate_request,
    configured_api_keys,
    extract_api_key,
    is_auth_bypass_enabled,
)


def test_configured_api_keys_returns_empty_when_unset() -> None:
    assert configured_api_keys({}) == []
    assert configured_api_keys({API_KEY_ENV: ""}) == []
    assert configured_api_keys({API_KEY_ENV: "  "}) == []


def test_configured_api_keys_parses_single_and_comma_separated() -> None:
    assert configured_api_keys({API_KEY_ENV: "solo-key"}) == ["solo-key"]
    assert configured_api_keys({API_KEY_ENV: " alpha , beta,gamma "}) == [
        "alpha",
        "beta",
        "gamma",
    ]


def test_is_auth_bypass_enabled_when_no_key() -> None:
    assert is_auth_bypass_enabled({}) is True


def test_is_auth_bypass_disabled_when_key_set() -> None:
    assert is_auth_bypass_enabled({API_KEY_ENV: "secret"}) is False


def test_explicit_bypass_wins_even_when_key_set() -> None:
    assert (
        is_auth_bypass_enabled(
            {
                API_KEY_ENV: "secret",
                AUTH_BYPASS_ENV: "true",
            }
        )
        is True
    )


def test_extract_api_key_reads_bearer_token() -> None:
    assert (
        extract_api_key(authorization="Bearer tok-1") == "tok-1"
    )


def test_extract_api_key_reads_x_api_key() -> None:
    assert extract_api_key(headers={"x-api-key": "tok-2"}) == "tok-2"


def test_extract_api_key_returns_none_when_missing() -> None:
    assert extract_api_key() is None


def test_api_key_matches() -> None:
    assert api_key_matches("abc", ["abc"]) is True
    assert api_key_matches("abc", ["zzz", "abc"]) is True
    assert api_key_matches("nope", ["abc"]) is False


def test_local_bypass_allows_unauthenticated_when_key_unset() -> None:
    user = authenticate_request(path="/runs/stream", env={})
    assert user["identity"] == "local-bypass"
    assert user["permissions"] == []


def test_rejects_unauthenticated_when_key_configured() -> None:
    env = {API_KEY_ENV: "test-secret-key"}
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request(path="/runs/stream", env=env)
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info2:
        authenticate_request(path="/assistants", env=env)
    assert exc_info2.value.status_code == 401


def test_rejects_wrong_bearer_token() -> None:
    env = {API_KEY_ENV: "test-secret-key"}
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request(
            path="/runs/stream",
            authorization="Bearer wrong",
            env=env,
        )
    assert exc_info.value.status_code == 401


def test_accepts_matching_bearer_token() -> None:
    env = {API_KEY_ENV: "test-secret-key"}
    user = authenticate_request(
        path="/runs/stream",
        authorization="Bearer test-secret-key",
        env=env,
    )
    assert user["identity"] == "api-key"


def test_accepts_matching_x_api_key() -> None:
    env = {API_KEY_ENV: "test-secret-key"}
    user = authenticate_request(
        path="/threads",
        headers={"x-api-key": "test-secret-key"},
        env=env,
    )
    assert user["identity"] == "api-key"


def test_get_ok_allowed_without_credentials_when_auth_on() -> None:
    env = {API_KEY_ENV: "test-secret-key"}
    user = authenticate_request(path="/ok", env=env)
    assert user["identity"] == "healthcheck"


def test_explicit_auth_bypass_allows_unauthenticated_with_key_set() -> None:
    env = {
        API_KEY_ENV: "test-secret-key",
        AUTH_BYPASS_ENV: "1",
    }
    user = authenticate_request(path="/runs/stream", env=env)
    assert user["identity"] == "local-bypass"
