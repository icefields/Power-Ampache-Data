# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Documented Ampache API error codes (spec intro section)."""
from enum import IntEnum


class ErrorCode(IntEnum):
    INVALID_HANDSHAKE = 4701
    ACCESS_DENIED = 4703
    NOT_FOUND = 4704
    DEPRECATED = 4706
    BAD_REQUEST = 4710
    # HTTP status surfaced as the error code when the server answers a failed
    # handshake with HTTP 401 instead of a spec envelope. Not a spec code.
    UNAUTHORIZED = 401
    # HTTP status surfaced as the error code when the server answers a stale
    # session token with HTTP 403 instead of the 4701 envelope. Not a spec code.
    FORBIDDEN = 403
