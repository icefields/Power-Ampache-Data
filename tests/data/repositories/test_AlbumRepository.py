"""Write-through storage: upsert -> read back by artistId ordered by year,
searchName; refresh semantics; sparse payloads."""
import json
import sqlite3

from ampachedata.data.db.Database import Database
from ampachedata.data.db.mappers.AlbumMapper import mapAlbum
from ampachedata.data.db.repositories.AlbumRepository import AlbumRepository


def _rows(payload):
    return [mapAlbum(album) for album in payload["album"]]


def testUpsertThenReadBack(dbPath, artistAlbumsPayload):
    repository = AlbumRepository(Database(dbPath))
    repository.upsertAlbums(_rows(artistAlbumsPayload))
    albums = repository.getAlbumsFromArtist("14")
    assert len(albums) == 1
    album = albums[0]
    assert album.id == "8"
    assert album.name == "Nofi Devices"
    assert album.basename == "Nofi Devices"
    assert album.artistId == "14"
    assert album.artistName == "Nofi/found."
    assert json.loads(album.artists) == artistAlbumsPayload["album"][0]["artists"]
    assert album.time == 4423
    assert album.year == 0
    assert album.songCount == 11
    assert album.diskCount == 1
    assert json.loads(album.genre) == artistAlbumsPayload["album"][0]["genre"]
    assert album.artUrl == "https://music.com.au/image.php?object_id=8&object_type=album&id=70&name=art.jpg"
    assert album.rating == 2
    assert album.averageRating == 0.0  # averagerating null -> 0.0


def testReadBackFiltersByArtistAndOrdersByYearThenSearchName(dbPath):
    repository = AlbumRepository(Database(dbPath))
    repository.upsertAlbums([
        mapAlbum({"id": "1", "name": "Beta", "year": 2001, "artist": {"id": "14", "name": "Nofi/found."}}),
        mapAlbum({"id": "2", "name": "Alpha", "year": 2001, "artist": {"id": "14", "name": "Nofi/found."}}),
        mapAlbum({"id": "3", "name": "Gamma", "year": 1999, "artist": {"id": "14", "name": "Nofi/found."}}),
        mapAlbum({"id": "4", "name": "Other", "year": 1980, "artist": {"id": "99", "name": "Someone Else"}}),
    ])
    albums = repository.getAlbumsFromArtist("14")
    assert [a.name for a in albums] == ["Gamma", "Alpha", "Beta"]


def testUpsertRefreshesNeverDuplicates(dbPath, artistAlbumsPayload):
    repository = AlbumRepository(Database(dbPath))
    repository.upsertAlbums(_rows(artistAlbumsPayload))
    rows = _rows(artistAlbumsPayload)
    rows[0]["songCount"] = 99
    repository.upsertAlbums(rows)
    count = sqlite3.connect(dbPath).execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0]
    assert count == 1
    assert repository.getAlbumsFromArtist("14")[0].songCount == 99


def testSparseAlbumMapsAndPersistsWithoutKeyError(dbPath):
    """Missing/empty optional fields (explicit null artist, no genre/art/...)
    must not raise; defaults land in the row."""
    repository = AlbumRepository(Database(dbPath))
    repository.upsertAlbums([mapAlbum({"id": "42", "name": "Sparse (Demo)", "artist": None})])
    album = repository.getAlbumsFromArtist("")[0]  # null artist -> artistId ""
    assert album.id == "42"
    assert album.artistId == ""
    assert album.artistName == ""
    assert album.artists == "[]"
    assert album.genre == "[]"
    assert album.artUrl == ""
    assert album.time == 0
    assert album.year == 0
    assert album.songCount == 0
    assert album.diskCount == 0
    assert album.rating == 0
    assert album.averageRating == 0.0
    row = sqlite3.connect(dbPath).execute(
        "SELECT searchName FROM AlbumEntity WHERE id = '42'"
    ).fetchone()
    assert row[0] == "Sparse Demo"  # parentheses stripped
