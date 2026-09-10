# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""artists.json artist objects -> ArtistEntity rows, incl. the silent-drop list."""
import pytest

from ampachedata.data.db.mappers.ArtistMapper import mapArtist

ARTIST_ENTITY_COLUMNS = {
    "id", "name", "albumCount", "songCount", "genre", "artUrl", "flag",
    "summary", "time", "yearFormed", "placeFormed", "multiUserId", "searchName",
}

DROPPED_FIELDS = ("prefix", "basename", "rating", "averagerating", "mbid", "has_art")


def testMapsEveryColumn(artistsPayload):
    row = mapArtist(artistsPayload["artist"][0])
    assert set(row.keys()) == ARTIST_ENTITY_COLUMNS
    assert row["id"] == "16"
    assert row["name"] == "CARNÚN"
    assert row["albumCount"] == 1
    assert row["songCount"] == 9
    assert row["genre"] == "[]"
    assert row["artUrl"] == "https://music.com.au/image.php?object_id=16&object_type=artist&id=134&name=art.jpg"
    assert row["flag"] == 0
    assert row["summary"].startswith("Formerly called DEFY CHRIST.")
    assert row["time"] == 3873
    assert row["yearFormed"] == 0
    assert row["placeFormed"] == ""
    assert row["multiUserId"] == ""
    assert row["searchName"] == "CARNÚN"


def testGenreFragmentIsVerbatimCompactJson(artistsPayload):
    row = mapArtist(artistsPayload["artist"][3])  # Comfort Fit
    assert row["genre"] == '[{"id":"8","name":"Hip-Hop"}]'


def testNullablesBecomeEmptyStrings(artistsPayload):
    row = mapArtist(artistsPayload["artist"][1])  # Chi.Otic: summary/placeformed null
    assert row["summary"] == ""
    assert row["placeFormed"] == ""


def testSearchNameStripsParentheses():
    row = mapArtist({"id": "1", "name": "A Beautiful Lie (Instrumental)"})
    assert row["searchName"] == "A Beautiful Lie Instrumental"


def testDroppedFieldsNeverAppear(artistsPayload):
    row = mapArtist(artistsPayload["artist"][0])
    for dropped in DROPPED_FIELDS:
        assert dropped not in row
