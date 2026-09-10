# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""First-run credentials bootstrap — the ONLY boundary where cleartext may exist.

Cleartext is accepted transiently (hidden prompt / stdin / env var via the CLI),
hashed with SHA256 in memory, and only the digest is persisted to the single
CredentialsEntity row. The cleartext is never stored, never logged, and never
appears in any error message. Every later re-auth uses the stored hash via
auth/SessionManager.py — this module is only the entry point."""
import re

from ..domain.Credentials import Credentials
from .auth.Handshake import sha256Hex
from .db.Database import Database
from .db.repositories.CredentialsRepository import CredentialsRepository
from .errors import CredentialValidationError

KEY_PATTERN = re.compile(r"[0-9a-f]{64}")


def storeCredentialsFromPassword(dbPath: str, username: str, serverUrl: str, cleartextPassword: str) -> None:
    """Hash cleartextPassword (SHA256, in memory) and persist only the digest.

    The cleartext is discarded immediately after hashing — never stored, never
    logged, never included in any exception. Raises CredentialValidationError on
    empty input, DatabaseError if dbPath does not exist."""
    if not cleartextPassword:
        raise CredentialValidationError("password must not be empty")
    passwordHash = sha256Hex(cleartextPassword)
    del cleartextPassword  # best-effort: drop our reference to the secret
    storeCredentialsFromKey(dbPath, username, serverUrl, passwordHash)


def storeCredentialsFromKey(dbPath: str, username: str, serverUrl: str, passwordHash: str) -> None:
    """Persist an already-hashed key. passwordHash must be exactly 64 lowercase
    hex chars — anything else raises CredentialValidationError (this also catches
    cleartext accidentally passed as a key)."""
    _requireNonEmpty(username, "username must not be empty")
    _requireServerUrl(serverUrl)
    if not KEY_PATTERN.fullmatch(passwordHash or ""):
        raise CredentialValidationError(
            "key must be exactly 64 lowercase hex characters (a SHA256 hex digest)"
        )
    database = Database(dbPath)
    try:
        CredentialsRepository(database).upsertCredentials(
            Credentials(
                username=username,
                passwordHash=passwordHash,
                authToken="",
                serverUrl=serverUrl,
            )
        )
    finally:
        database.close()


def _requireNonEmpty(value, message: str) -> None:
    if not value or not value.strip():
        raise CredentialValidationError(message)


def _requireServerUrl(serverUrl) -> None:
    if not serverUrl or not serverUrl.startswith(("http://", "https://")):
        raise CredentialValidationError("serverUrl must be a non-empty http(s) URL")
