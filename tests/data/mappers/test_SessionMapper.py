"""handshake.json -> SessionEntity row, incl. the silent-drop list."""
from ampachedata.data.db.mappers.SessionMapper import SESSION_PRIMARY_KEY, mapSession

SESSION_ENTITY_COLUMNS = {
    "primaryKey", "add", "albums", "api", "artists", "auth", "catalogs", "clean",
    "genres", "labels", "licenses", "liveStreams", "playlists", "playlistsSearches",
    "podcastEpisodes", "podcasts", "searches", "sessionExpire", "shares", "songs",
    "update", "users", "videos",
}

DROPPED_FIELDS = (
    "streamtoken", "max_song", "max_album", "max_artist", "max_video",
    "max_podcast", "max_podcast_episode", "username",
)


def testHandshakeExampleMapsToSessionEntityRow(handshakePayload):
    row = mapSession(handshakePayload)
    assert set(row.keys()) == SESSION_ENTITY_COLUMNS
    assert row["primaryKey"] == SESSION_PRIMARY_KEY
    assert row["auth"] == "0c45633f51b0e264a2260ebfa406e1ad"
    assert row["api"] == "8.0.0"
    assert row["sessionExpire"] == "2022-08-17T06:21:00+00:00"
    assert row["add"] == "2021-08-03T00:04:14+00:00"
    assert row["songs"] == 75
    assert row["albums"] == 9
    assert row["artists"] == 19
    assert row["playlistsSearches"] == 22
    assert row["podcastEpisodes"] == 13
    assert row["liveStreams"] == 2
    assert row["labels"] == 3


def testDroppedFieldsNeverAppear(handshakePayload):
    row = mapSession(handshakePayload)
    for dropped in DROPPED_FIELDS:
        assert dropped not in row
