# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Domain representation of CredentialsEntity. passwordHash is SHA256(password) —
the KEY. Cleartext never exists in this system."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Credentials:
    username: str
    passwordHash: str
    authToken: str
    serverUrl: str
