# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""playlists.json/playlist.json playlist objects -> PlaylistEntity rows,
incl. the silent-drop list."""
from ampachedata.data.db.mappers.PlaylistMapper import mapPlaylist

PLAYLIST_ENTITY_COLUMNS = {
    "id", "name", "owner", "items", "type", "artUrl", "flag",
    "preciseRating", "rating", "averageRating", "multiUserId",
}

DROPPED_FIELDS = (
    "has_access", "has_collaborate", "has_art", "md5", "last_update", "time",
    "user", "playlist_folder_id", "playlist_folder_sort_order",
)


def testMapsEveryColumn(playlistsPayload):
    row = mapPlaylist(playlistsPayload["playlist"][0])
    assert set(row.keys()) == PLAYLIST_ENTITY_COLUMNS
    assert row["id"] == "4"
    assert row["name"] == "random - user - private"
    assert row["owner"] == "user"  # plain string in the response
    assert row["items"] == 43
    assert row["type"] == "private"
    assert row["artUrl"] == "https://music.com.au/images/blankalbum_128x128.png"
    assert row["flag"] == 0
    assert row["preciseRating"] == 0.0  # playlists carry no preciserating field
    assert row["rating"] == 0           # null -> 0
    assert row["averageRating"] == 0.0  # null -> 0.0
    assert row["multiUserId"] == ""


def testSinglePlaylistExampleMaps(playlistPayload):
    row = mapPlaylist(playlistPayload)
    assert row["id"] == "127"
    assert row["name"] == "renamejson"
    assert row["owner"] == "user"
    assert row["items"] == 0
    assert row["type"] == "private"


def testItemsAsArrayStoresLength():
    # spec allows items as array<object>; the column is INTEGER
    row = mapPlaylist({"id": "1", "items": [{"id": "1"}, {"id": "2"}]})
    assert row["items"] == 2


def testSparsePlaylistDefaults():
    row = mapPlaylist({"id": "9"})
    assert row["name"] == ""
    assert row["owner"] == ""
    assert row["items"] == 0
    assert row["type"] == ""
    assert row["artUrl"] == ""
    assert row["flag"] == 0
    assert row["rating"] == 0
    assert row["averageRating"] == 0.0


def testDroppedFieldsNeverAppear(playlistsPayload):
    row = mapPlaylist(playlistsPayload["playlist"][0])
    for dropped in DROPPED_FIELDS:
        assert dropped not in row
