# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""handshake/ping response JSON -> SessionEntity row dict.

Dropped per Field Mapping (no SessionEntity column — silent, by design):
streamtoken, max_song, max_album, max_artist, max_video, max_podcast,
max_podcast_episode, username."""

SESSION_PRIMARY_KEY = "session"  # SessionEntity is single-row; fixed PK value

_STRING_FIELDS = {
    "auth": "auth",
    "api": "api",
    "session_expire": "sessionExpire",
    "add": "add",
    "update": "update",
    "clean": "clean",
}

_COUNT_FIELDS = {
    "songs": "songs",
    "albums": "albums",
    "artists": "artists",
    "genres": "genres",
    "playlists": "playlists",
    "searches": "searches",
    "playlists_searches": "playlistsSearches",
    "users": "users",
    "catalogs": "catalogs",
    "videos": "videos",
    "podcasts": "podcasts",
    "podcast_episodes": "podcastEpisodes",
    "shares": "shares",
    "licenses": "licenses",
    "live_streams": "liveStreams",
    "labels": "labels",
}


def mapSession(payload: dict) -> dict:
    row = {"primaryKey": SESSION_PRIMARY_KEY}
    for jsonKey, column in _STRING_FIELDS.items():
        row[column] = payload.get(jsonKey) or ""
    for jsonKey, column in _COUNT_FIELDS.items():
        row[column] = int(payload.get(jsonKey) or 0)
    return row
