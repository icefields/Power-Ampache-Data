# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Pure passphrase construction. No I/O, no DB, no transport.

passphrase = SHA256(timestamp + KEY), where KEY = SHA256(password) is already
stored in CredentialsEntity.password. Cleartext is never stored, logged, or requested."""
import hashlib


def sha256Hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def buildPassphrase(timestamp: str, passwordHash: str) -> str:
    return sha256Hex(timestamp + passwordHash)
