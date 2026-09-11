# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""ampachedata — public API. Anything not re-exported here is private."""
from .data.AmpacheClient import AmpacheClient
from .data.Bootstrap import storeCredentialsFromKey, storeCredentialsFromPassword
from .data.Schema import createDatabase
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
from .data.db.Database import Database
from .data.db.repositories.ArtistRepository import ArtistRepository
from .data.db.repositories.AlbumRepository import AlbumRepository
from .data.db.repositories.SongRepository import SongRepository
from .data.db.repositories.PlaylistRepository import PlaylistRepository

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
    "Database",
    "ArtistRepository",
    "AlbumRepository",
    "SongRepository",
    "PlaylistRepository",
    "storeCredentialsFromPassword",
    "storeCredentialsFromKey",
    "createDatabase",
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
