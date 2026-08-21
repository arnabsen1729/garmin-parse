"""Garmin Connect authentication helpers.

Wraps ``garminconnect.Garmin`` login so that:

* On first run the user is prompted (interactively) for their email,
  password, and (if Garmin requires it) an MFA code.
* On subsequent runs, cached session tokens stored at ``tokenstore``
  (managed entirely by the underlying ``garminconnect``/``garth`` library)
  are reused, so the user is not prompted again until those tokens expire.
* Credentials are never written to disk and never logged. Only the
  library's own token cache file at ``tokenstore`` persists anything.
* When run non-interactively (no TTY on stdin, e.g. in CI), a failed
  cached-token login raises ``GarminAuthError`` immediately instead of
  attempting to prompt for credentials.
"""

from __future__ import annotations

import getpass
import sys

from garminconnect import Garmin
from garminconnect.exceptions import GarminConnectAuthenticationError

DEFAULT_TOKENSTORE = "~/.garminconnect"


class GarminAuthError(RuntimeError):
    """Raised when Garmin login ultimately fails."""


def _prompt_mfa() -> str:
    """Read an MFA code from the user via stdin."""
    return input("Enter MFA code: ")


def _prompt_credentials() -> tuple[str, str]:
    """Interactively prompt for Garmin email and password.

    The password is read with ``getpass.getpass`` so it is never echoed to
    the terminal and never captured via a plain ``input()`` call.
    """
    email = input("Garmin Connect email: ")
    password = getpass.getpass("Garmin Connect password: ")
    return email, password


def get_client(tokenstore: str = DEFAULT_TOKENSTORE) -> Garmin:
    """Return an authenticated ``garminconnect.Garmin`` client.

    Tries to resume a session from cached tokens at ``tokenstore`` first
    (no prompting). If no valid cached session exists, prompts for email
    and password, and for an MFA code if Garmin requires one, then persists
    the resulting session to ``tokenstore`` (handled internally by
    ``Garmin.login``) so future calls skip the prompts.

    If cached-token login fails and stdin is not an interactive terminal
    (e.g. running in CI), raises ``GarminAuthError`` immediately rather
    than attempting to prompt for credentials.

    Raises:
        GarminAuthError: if login ultimately fails (e.g. wrong
            credentials, MFA code rejected, network/API error), or if
            cached tokens are invalid/missing and no interactive
            terminal is available to prompt for credentials.
    """
    # First, try to resume purely from cached tokens: no credentials are
    # supplied, so this only succeeds if `tokenstore` already holds a
    # valid, non-expired session.
    client = Garmin(prompt_mfa=_prompt_mfa)
    try:
        client.login(tokenstore=tokenstore)
        return client
    except GarminConnectAuthenticationError:
        # No usable cached tokens (or they were rejected and no credentials
        # were available to refresh them). Fall through to a fresh,
        # credential-based login.
        pass
    except Exception as exc:  # noqa: BLE001 - re-raised with context below
        raise GarminAuthError(f"Garmin login failed: {exc}") from exc

    if not sys.stdin.isatty():
        raise GarminAuthError(
            "Cached Garmin session is invalid or expired, and no "
            "interactive terminal is available to log in. Run "
            "`garmin-parse sync` locally to refresh it, then update the "
            "`GARMIN_TOKENSTORE` secret."
        )

    email, password = _prompt_credentials()
    client = Garmin(email, password, prompt_mfa=_prompt_mfa)
    try:
        client.login(tokenstore=tokenstore)
    except Exception as exc:  # noqa: BLE001 - normalize into one error type
        raise GarminAuthError(
            "Garmin login failed. Check your email/password and MFA code. "
            f"Original error: {exc}"
        ) from exc

    return client
