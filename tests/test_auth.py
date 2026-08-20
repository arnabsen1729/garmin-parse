"""Unit tests for garmin_parse.auth.

No real Garmin credentials are available in this environment, so
``garminconnect.Garmin`` is mocked entirely. These tests verify the
control flow (cache hit vs. cache miss -> prompt), that the MFA callback
reads via ``input()``, and that the password is never read via
``input()`` (only ``getpass.getpass``).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from garminconnect.exceptions import GarminConnectAuthenticationError

from garmin_parse import auth


def test_get_client_uses_cached_tokens_without_prompting():
    """If cached tokens are valid, login succeeds with no credentials."""
    mock_client = MagicMock()
    mock_client.login.return_value = (None, None)

    with (
        patch("garmin_parse.auth.Garmin", return_value=mock_client) as garmin_cls,
        patch("builtins.input") as mock_input,
        patch("getpass.getpass") as mock_getpass,
    ):
        result = auth.get_client(tokenstore="/tmp/fake-tokenstore")

    assert result is mock_client
    # Only one Garmin() construction: no fallback credential login needed.
    garmin_cls.assert_called_once_with(prompt_mfa=auth._prompt_mfa)
    mock_client.login.assert_called_once_with(tokenstore="/tmp/fake-tokenstore")
    mock_input.assert_not_called()
    mock_getpass.assert_not_called()


def test_get_client_prompts_for_credentials_when_no_cached_tokens():
    """If there is no valid cached session, prompt for email/password and retry."""
    cache_miss_client = MagicMock()
    cache_miss_client.login.side_effect = GarminConnectAuthenticationError(
        "Username and password are required"
    )

    fresh_client = MagicMock()
    fresh_client.login.return_value = (None, None)

    created_clients = [cache_miss_client, fresh_client]

    def fake_garmin(*args, **kwargs):
        return created_clients.pop(0)

    with (
        patch("garmin_parse.auth.Garmin", side_effect=fake_garmin) as garmin_cls,
        patch("builtins.input", return_value="user@example.com") as mock_input,
        patch("getpass.getpass", return_value="super-secret") as mock_getpass,
    ):
        result = auth.get_client(tokenstore="/tmp/fake-tokenstore")

    assert result is fresh_client
    assert garmin_cls.call_count == 2
    # Second construction uses freshly prompted credentials.
    _, kwargs = garmin_cls.call_args_list[1]
    args = garmin_cls.call_args_list[1].args
    assert args[0] == "user@example.com"
    assert args[1] == "super-secret"
    assert kwargs["prompt_mfa"] is auth._prompt_mfa

    mock_input.assert_called_once_with("Garmin Connect email: ")
    mock_getpass.assert_called_once_with("Garmin Connect password: ")
    fresh_client.login.assert_called_once_with(tokenstore="/tmp/fake-tokenstore")


def test_get_client_raises_clear_error_on_final_failure():
    """A login failure even with fresh credentials raises GarminAuthError."""
    cache_miss_client = MagicMock()
    cache_miss_client.login.side_effect = GarminConnectAuthenticationError(
        "Username and password are required"
    )

    fresh_client = MagicMock()
    fresh_client.login.side_effect = GarminConnectAuthenticationError(
        "Authentication failed (401 Unauthorized)"
    )

    created_clients = [cache_miss_client, fresh_client]

    def fake_garmin(*args, **kwargs):
        return created_clients.pop(0)

    with (
        patch("garmin_parse.auth.Garmin", side_effect=fake_garmin),
        patch("builtins.input", return_value="user@example.com"),
        patch("getpass.getpass", return_value="wrong-password"),
    ):
        with pytest.raises(auth.GarminAuthError):
            auth.get_client(tokenstore="/tmp/fake-tokenstore")


def test_prompt_mfa_reads_code_via_input():
    """The prompt_mfa callback passed to Garmin() must use input()."""
    with patch("builtins.input", return_value="123456") as mock_input:
        code = auth._prompt_mfa()

    assert code == "123456"
    mock_input.assert_called_once_with("Enter MFA code: ")


def test_prompt_credentials_never_reads_password_via_input():
    """Password must always come from getpass.getpass, never input()."""
    with (
        patch("builtins.input", return_value="user@example.com") as mock_input,
        patch("getpass.getpass", return_value="super-secret") as mock_getpass,
    ):
        email, password = auth._prompt_credentials()

    assert email == "user@example.com"
    assert password == "super-secret"
    mock_getpass.assert_called_once()
    # input() was only used for the email prompt, never for the password.
    mock_input.assert_called_once_with("Garmin Connect email: ")
