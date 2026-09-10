# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""ampachedata — public API. Anything not re-exported here is private."""
from .data.AmpacheClient import AmpacheClient
from .data.Bootstrap import storeCredentialsFromKey, storeCredentialsFromPassword
from .data.ObjectType import ObjectType
from .data.errors import (
    AccessDeniedError,
    AmpacheError,
    ApiError,
    BadRequestError,
    CacheVerificationError,
    CredentialValidationError,
    DatabaseError,
    DeprecatedError,
    InvalidHandshakeError,
    NotFoundError,
    UnknownApiError,
)
from .domain.Artist import Artist
from .domain.Album import Album
from .domain.Credentials import Credentials
from .domain.History import History
from .domain.OperationResult import OperationResult
from .domain.PageResult import PageResult
from .domain.PingResult import PingResult
from .domain.Playlist import Playlist
from .domain.PlaylistSong import PlaylistSong
from .domain.Session import Session
from .domain.Song import Song

__all__ = [
    "AmpacheClient",
    "Artist",
    "Album",
    "Song",
    "Playlist",
    "PlaylistSong",
    "History",
    "Session",
    "Credentials",
    "PingResult",
    "OperationResult",
    "PageResult",
    "ObjectType",
    "storeCredentialsFromPassword",
    "storeCredentialsFromKey",
    "AmpacheError",
    "ApiError",
    "DatabaseError",
    "InvalidHandshakeError",
    "AccessDeniedError",
    "NotFoundError",
    "DeprecatedError",
    "BadRequestError",
    "CredentialValidationError",
    "CacheVerificationError",
    "UnknownApiError",
]
