"""Documented Ampache API error codes (spec intro section)."""
from enum import IntEnum


class ErrorCode(IntEnum):
    INVALID_HANDSHAKE = 4701
    ACCESS_DENIED = 4703
    NOT_FOUND = 4704
    DEPRECATED = 4706
    BAD_REQUEST = 4710
