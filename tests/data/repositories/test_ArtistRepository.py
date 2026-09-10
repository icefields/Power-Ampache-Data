# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Write-through storage: upsert -> read back ordered by searchName; refresh semantics."""
import sqlite3

from ampachedata.data.db.Database import Database
from ampachedata.data.db.mappers.ArtistMapper import mapArtist
from ampachedata.data.db.repositories.ArtistRepository import ArtistRepository


def _rows(payload):
    return [mapArtist(artist) for artist in payload["artist"]]


def testUpsertThenReadBackOrderedBySearchName(dbPath, artistsPayload):
    repository = ArtistRepository(Database(dbPath))
    repository.upsertArtists(_rows(artistsPayload))
    artists = repository.getArtists()
    assert [a.name for a in artists] == ["CARNÚN", "Chi.Otic", "Comedown Kid", "Comfort Fit"]
    first = artists[0]
    assert first.id == "16"
    assert first.albumCount == 1
    assert first.songCount == 9
    assert first.genre == "[]"
    assert first.artUrl == "https://music.com.au/image.php?object_id=16&object_type=artist&id=134&name=art.jpg"
    assert first.summary.startswith("Formerly called DEFY CHRIST.")
    assert first.time == 3873
    assert first.yearFormed == 0
    assert first.placeFormed == ""


def testUpsertRefreshesNeverDuplicates(dbPath, artistsPayload):
    repository = ArtistRepository(Database(dbPath))
    repository.upsertArtists(_rows(artistsPayload))
    rows = _rows(artistsPayload)
    rows[0]["songCount"] = 99
    repository.upsertArtists(rows)
    count = sqlite3.connect(dbPath).execute("SELECT COUNT(*) FROM ArtistEntity").fetchone()[0]
    assert count == 4
    assert repository.getArtists()[0].songCount == 99


def testReadBackReturnsAllRowsNotJustUpserted(dbPath, artistsPayload):
    repository = ArtistRepository(Database(dbPath))
    repository.upsertArtists(_rows(artistsPayload))
    repository.upsertArtists([mapArtist({"id": "99", "name": "Aardvark"})])
    artists = repository.getArtists()
    assert len(artists) == 5
    assert artists[0].name == "Aardvark"  # ORDER BY searchName, not insertion order
