import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from supabase import AuthApiError, AuthRetryableError

from app import auth


@pytest.mark.parametrize(
    ("provider_error", "expected_status"),
    [
        (AuthApiError("Expired JWT", 401, "bad_jwt"), 401),
        (AuthApiError("Revoked session", 403, "session_not_found"), 401),
        (AuthRetryableError("Connection timed out", 0), 503),
        (AuthApiError("Rate limited", 429, "over_request_rate_limit"), 503),
        (AuthApiError("Service unavailable", 500, "unexpected_failure"), 503),
    ],
)
def test_get_current_user_distinguishes_invalid_token_from_provider_failure(
    monkeypatch, provider_error, expected_status
):
    def get_user(_token):
        raise provider_error

    monkeypatch.setattr(auth.supabase.auth, "get_user", get_user)

    with pytest.raises(HTTPException) as caught:
        auth.get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials="synthetic-token"))

    assert caught.value.status_code == expected_status
    assert caught.value.headers == ({"WWW-Authenticate": "Bearer"} if expected_status == 401 else None)
