# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""API method names — no magic strings outside this enum."""
from enum import Enum


class ApiMethod(str, Enum):
    HANDSHAKE = "handshake"
    PING = "ping"
    GOODBYE = "goodbye"
    ARTISTS = "artists"
    ARTIST = "artist"
    ARTIST_ALBUMS = "artist_albums"
    ARTIST_SONGS = "artist_songs"
    ALBUMS = "albums"
    ALBUM = "album"
    ALBUM_SONGS = "album_songs"
    SONGS = "songs"
    SONG = "song"
    PLAYLISTS = "playlists"
    PLAYLIST = "playlist"
    PLAYLIST_SONGS = "playlist_songs"
    STATS = "stats"
    STREAM = "stream"
    DOWNLOAD = "download"
    FLAG = "flag"
    RATE = "rate"
