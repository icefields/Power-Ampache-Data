# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Write-through storage for PlaylistEntity: upsert -> read back ordered by
(name, id); refresh semantics; single-row read-back."""
import sqlite3

from ampachedata.data.db.Database import Database
from ampachedata.data.db.mappers.PlaylistMapper import mapPlaylist
from ampachedata.data.db.repositories.PlaylistRepository import PlaylistRepository


def testUpsertThenReadBack(dbPath, playlistsPayload):
    repository = PlaylistRepository(Database(dbPath))
    repository.upsertPlaylists([mapPlaylist(p) for p in playlistsPayload["playlist"]])
    playlists = repository.getPlaylists()
    assert len(playlists) == 1
    playlist = playlists[0]
    assert playlist.id == "4"
    assert playlist.name == "random - user - private"
    assert playlist.owner == "user"
    assert playlist.items == 43
    assert playlist.type == "private"
    assert playlist.artUrl == "https://music.com.au/images/blankalbum_128x128.png"
    assert playlist.rating == 0
    assert playlist.preciseRating == 0.0
    assert playlist.averageRating == 0.0


def testReadBackOrderedByNameThenId(dbPath):
    repository = PlaylistRepository(Database(dbPath))
    repository.upsertPlaylists([
        mapPlaylist({"id": "1", "name": "Beta"}),
        mapPlaylist({"id": "2", "name": "Alpha"}),
        mapPlaylist({"id": "3", "name": "Alpha"}),
    ])
    assert [(p.name, p.id) for p in repository.getPlaylists()] == [
        ("Alpha", "2"), ("Alpha", "3"), ("Beta", "1"),
    ]


def testGetPlaylistByIdAndMissing(dbPath, playlistPayload):
    repository = PlaylistRepository(Database(dbPath))
    assert repository.getPlaylist("127") is None
    repository.upsertPlaylists([mapPlaylist(playlistPayload)])
    playlist = repository.getPlaylist("127")
    assert playlist.name == "renamejson"
    assert playlist.items == 0


def testUpsertRefreshesNeverDuplicates(dbPath, playlistsPayload):
    repository = PlaylistRepository(Database(dbPath))
    repository.upsertPlaylists([mapPlaylist(p) for p in playlistsPayload["playlist"]])
    row = mapPlaylist(playlistsPayload["playlist"][0])
    row["name"] = "renamed"
    repository.upsertPlaylists([row])
    assert sqlite3.connect(dbPath).execute(
        "SELECT COUNT(*) FROM PlaylistEntity"
    ).fetchone()[0] == 1
    assert repository.getPlaylist("4").name == "renamed"
