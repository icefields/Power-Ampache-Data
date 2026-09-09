"""PlaylistSongEntity join rows: upsert refreshes positions in place; the
SongRepository join read-back returns songs in position order."""
import sqlite3

from ampachedata.data.db.Database import Database
from ampachedata.data.db.mappers.PlaylistSongMapper import mapPlaylistSong
from ampachedata.data.db.mappers.SongMapper import mapSong
from ampachedata.data.db.repositories.PlaylistSongRepository import PlaylistSongRepository
from ampachedata.data.db.repositories.SongRepository import SongRepository


def _seed(dbPath, playlistSongsPayload, playlistId="4"):
    database = Database(dbPath)
    songs = playlistSongsPayload["song"]
    SongRepository(database).upsertSongs([mapSong(song) for song in songs])
    PlaylistSongRepository(database).upsertPlaylistSongs(
        [mapPlaylistSong(song, playlistId) for song in songs]
    )
    return database


def testUpsertThenReadBackInPositionOrder(dbPath, playlistSongsPayload):
    database = _seed(dbPath, playlistSongsPayload)
    songs = SongRepository(database).getPlaylistSongs("4")
    assert [song.id for song in songs] == ["91", "101", "62", "89"]
    assert [song.title for song in songs] == [
        "Home Capsules", "Rehearsal Tape (1996)", "PurpleSmoke", "Stolen",
    ]


def testReadBackOrdersByPositionNotPayloadOrder(dbPath):
    """Array order != position order: the read-back follows position, and the
    stored positions are exactly what the payload gave (no renumbering)."""
    database = Database(dbPath)
    songs = [
        {"id": "1", "title": "Third", "playlisttrack": 3},
        {"id": "2", "title": "First", "playlisttrack": 1},
        {"id": "3", "title": "Second", "playlisttrack": 2},
    ]
    SongRepository(database).upsertSongs([mapSong(song) for song in songs])
    PlaylistSongRepository(database).upsertPlaylistSongs(
        [mapPlaylistSong(song, "9") for song in songs]
    )
    readBack = SongRepository(database).getPlaylistSongs("9")
    assert [song.title for song in readBack] == ["First", "Second", "Third"]
    rows = sqlite3.connect(dbPath).execute(
        "SELECT songId, position FROM PlaylistSongEntity ORDER BY position"
    ).fetchall()
    assert rows == [("2", 1), ("3", 2), ("1", 3)]


def testUpsertRefreshesPositionNeverDuplicates(dbPath, playlistSongsPayload):
    database = _seed(dbPath, playlistSongsPayload)
    moved = mapPlaylistSong(playlistSongsPayload["song"][0], "4")
    moved["position"] = 99
    PlaylistSongRepository(database).upsertPlaylistSongs([moved])
    connection = sqlite3.connect(dbPath)
    assert connection.execute(
        "SELECT COUNT(*) FROM PlaylistSongEntity"
    ).fetchone()[0] == 4
    assert connection.execute(
        "SELECT position FROM PlaylistSongEntity WHERE id = '4:91'"
    ).fetchone()[0] == 99


def testOtherPlaylistsJoinRowsAreInvisible(dbPath, playlistSongsPayload):
    database = _seed(dbPath, playlistSongsPayload, playlistId="4")
    song = playlistSongsPayload["song"][0]
    PlaylistSongRepository(database).upsertPlaylistSongs([mapPlaylistSong(song, "5")])
    assert [s.id for s in SongRepository(database).getPlaylistSongs("4")] == [
        "91", "101", "62", "89",
    ]
    assert [s.id for s in SongRepository(database).getPlaylistSongs("5")] == ["91"]
