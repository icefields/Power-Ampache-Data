"""playlist_songs.json song entries -> PlaylistSongEntity join rows.

position is the payload's playlisttrack, verbatim — never renumbered."""
from ampachedata.data.db.mappers.PlaylistSongMapper import mapPlaylistSong


def testMapsJoinRowFromFixture(playlistSongsPayload):
    row = mapPlaylistSong(playlistSongsPayload["song"][0], "4")
    assert row == {
        "id": "4:91",
        "songId": "91",
        "playlistId": "4",
        "position": 1,
        "multiUserId": "",
    }


def testPositionsAreVerbatimNeverRenumbered(playlistSongsPayload):
    rows = [mapPlaylistSong(song, "4") for song in playlistSongsPayload["song"]]
    assert [row["position"] for row in rows] == [1, 2, 3, 4]
    assert [row["songId"] for row in rows] == ["91", "101", "62", "89"]


def testMissingPlaylistTrackDefaultsToZero():
    row = mapPlaylistSong({"id": "5"}, "7")
    assert row["id"] == "7:5"
    assert row["position"] == 0
