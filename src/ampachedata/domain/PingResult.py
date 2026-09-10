# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Result of ping (health check / expiry probe)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PingResult:
    authenticated: bool
    auth: str = ""
    sessionExpire: str = ""
    api: str = ""
    server: str = ""
    version: str = ""
    compatible: str = ""
