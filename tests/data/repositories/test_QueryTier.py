"""Query tier: DB-only reads over the existing repositories. No transport —
scratch DBs are seeded by upserting example fixtures and synthetic payloads
through the existing mappers, then read back via the query methods."""
import pytest

from ampachedata.data.db.Database import Database
from ampachedata.data.db.mappers.AlbumMapper import mapAlbum
from ampachedata.data.db.mappers.ArtistMapper import mapArtist
from ampachedata.data.db.mappers.HistoryMapper import mapHistory
from ampachedata.data.db.mappers.PlaylistMapper import mapPlaylist
from ampachedata.data.db.mappers.PlaylistSongMapper import mapPlaylistSong
from ampachedata.data.db.mappers.SongMapper import mapSong
from ampachedata.data.db.repositories.AlbumRepository import AlbumRepository
from ampachedata.data.db.repositories.ArtistRepository import ArtistRepository
from ampachedata.data.db.repositories.HistoryRepository import HistoryRepository
from ampachedata.data.db.repositories.PlaylistRepository import PlaylistRepository
from ampachedata.data.db.repositories.PlaylistSongRepository import PlaylistSongRepository
from ampachedata.data.db.repositories.SongRepository import SongRepository


@pytest.fixture
def database(dbPath):
    db = Database(dbPath)
    yield db
    db.close()


def _song(songId, title, artistId="a1", artistName="Artist One",
          albumId="al1", albumName="Album One", lastPlayed=None, playcount=0):
    song = {
        "id": songId,
        "title": title,
        "artist": {"id": artistId, "name": artistName},
        "album": {"id": albumId, "name": albumName},
        "playcount": playcount,
    }
    if lastPlayed is not None:
        song["last_played"] = lastPlayed
    return song


def _album(albumId, name, year):
    return {"id": albumId, "name": name, "year": year,
            "artist": {"id": "a1", "name": "Artist One"}}


def _seedSongs(database, songs):
    SongRepository(database).upsertSongs([mapSong(s) for s in songs])
    histories = [h for h in (mapHistory(s) for s in songs) if h is not None]
    if histories:
        HistoryRepository(database).upsertHistories(histories)


# --- list methods: all rows, documented order --------------------------------

def testListArtistsOrderedBySearchName(database, artistsPayload):
    repository = ArtistRepository(database)
    repository.upsertArtists([mapArtist(a) for a in artistsPayload["artist"]])
    assert [a.name for a in repository.listArtists()] == [
        "CARNÚN", "Chi.Otic", "Comedown Kid", "Comfort Fit",
    ]


def testListAlbumsOrderedByYearThenSearchName(database):
    repository = AlbumRepository(database)
    repository.upsertAlbums([
        mapAlbum(_album("1", "Zulu", 1999)),
        mapAlbum(_album("2", "Alpha", 2001)),
        mapAlbum(_album("3", "Beta", 1999)),
    ])
    assert [a.name for a in repository.listAlbums()] == ["Beta", "Zulu", "Alpha"]


def testListPlaylistsOrderedByName(database):
    repository = PlaylistRepository(database)
    repository.upsertPlaylists([
        mapPlaylist({"id": "1", "name": "Zulu"}),
        mapPlaylist({"id": "2", "name": "Alpha"}),
    ])
    assert [p.name for p in repository.listPlaylists()] == ["Alpha", "Zulu"]


def testPlaylistSongsReturnsPositionOrder(database):
    payload = [
        {"id": "s1", "title": "One", "playlisttrack": 2},
        {"id": "s2", "title": "Two", "playlisttrack": 1},
        {"id": "s3", "title": "Three", "playlisttrack": 3},
    ]
    SongRepository(database).upsertSongs([mapSong(s) for s in payload])
    PlaylistSongRepository(database).upsertPlaylistSongs(
        [mapPlaylistSong(s, "4") for s in payload]
    )
    songs = SongRepository(database).playlistSongs("4")
    assert [s.title for s in songs] == ["Two", "One", "Three"]


# --- listSongs: ordering, windows, filters, total ----------------------------

def testListSongsTitleOrderAndTotal(database):
    _seedSongs(database, [
        _song("s1", "Gamma"),
        _song("s2", "Alpha"),
        _song("s3", "Beta"),
    ])
    page = SongRepository(database).listSongs()
    assert [s.title for s in page.rows] == ["Alpha", "Beta", "Gamma"]
    assert page.total == 3


def testListSongsOffsetWindowsAreStable(database):
    _seedSongs(database, [
        _song("s5", "Epsilon"),
        _song("s4", "Delta"),
        _song("s3", "Gamma"),
        _song("s2", "Beta"),
        _song("s1", "Alpha"),
    ])
    repository = SongRepository(database)
    first = repository.listSongs(limit=2)
    second = repository.listSongs(limit=2, offset=2)
    third = repository.listSongs(limit=2, offset=4)
    # searchTitle order is LEXICOGRAPHIC: Alpha, Beta, Delta, Epsilon, Gamma —
    # not Greek-alphabet order (SQL never sorts Gamma before Delta).
    assert [s.title for s in first.rows] == ["Alpha", "Beta"]
    assert [s.title for s in second.rows] == ["Delta", "Epsilon"]
    assert [s.title for s in third.rows] == ["Gamma"]
    assert first.total == second.total == third.total == 5


def testListSongsFiltersAndTotalMatchesSqlCount(database):
    _seedSongs(database, [
        _song("s1", "One", artistId="a1", artistName="Solo",
              albumId="al1", albumName="First"),
        _song("s2", "Two", artistId="a1", artistName="Solo",
              albumId="al2", albumName="Second"),
        _song("s3", "Three", artistId="a2", artistName="Duo",
              albumId="al3", albumName="Third"),
    ])
    repository = SongRepository(database)
    byArtist = repository.listSongs(artistId="a1")
    assert [s.title for s in byArtist.rows] == ["One", "Two"]
    expected = database.connection.execute(
        "SELECT COUNT(*) FROM SongEntity WHERE artistId = 'a1'"
    ).fetchone()[0]
    assert byArtist.total == expected == 2
    byAlbum = repository.listSongs(albumId="al2")
    assert [s.title for s in byAlbum.rows] == ["Two"]
    assert byAlbum.total == 1
    combined = repository.listSongs(artistId="a1", albumId="al2")
    assert [s.title for s in combined.rows] == ["Two"]
    assert combined.total == 1


def testListSongsArtistOrder(database):
    _seedSongs(database, [
        _song("s1", "B Song", artistName="Zeta"),
        _song("s2", "A Song", artistName="Alpha"),
    ])
    page = SongRepository(database).listSongs(order="artist")
    assert [s.title for s in page.rows] == ["A Song", "B Song"]


def testListSongsAlbumOrderIsAlbumThenDiskTrack(database):
    _seedSongs(database, [
        {**_song("s1", "Second", albumName="A Album", albumId="al1"), "track": 2},
        {**_song("s2", "First", albumName="A Album", albumId="al1"), "track": 1},
        _song("s3", "Other", albumName="B Album", albumId="al2"),
    ])
    page = SongRepository(database).listSongs(order="album")
    assert [s.title for s in page.rows] == ["First", "Second", "Other"]


def testListSongsRecentOrderPlayedFirstNeverPlayedLast(database):
    _seedSongs(database, [
        _song("s1", "Old", lastPlayed="2023-01-01T00:00:00+00:00", playcount=2),
        _song("s2", "New", lastPlayed="2024-06-01T00:00:00+00:00", playcount=5),
        _song("s3", "Never"),
    ])
    page = SongRepository(database).listSongs(order="recent")
    assert [s.title for s in page.rows] == ["New", "Old", "Never"]
    assert page.total == 3


def testListSongsUnknownOrderRaises(database):
    _seedSongs(database, [_song("s1", "One")])
    with pytest.raises(ValueError):
        SongRepository(database).listSongs(order="year; DROP TABLE SongEntity")


# --- search ------------------------------------------------------------------

def testSearchSongsMatchesTitleArtistAndAlbumCaseInsensitiveAscii(database):
    _seedSongs(database, [
        _song("s1", "100% Pure", artistName="The Percent", albumName="Fractions"),
        _song("s2", "Plain Song", artistName="Someone", albumName="Elsewhere"),
    ])
    repository = SongRepository(database)
    assert [s.title for s in repository.searchSongs("pure").rows] == ["100% Pure"]
    assert [s.title for s in repository.searchSongs("PERCENT").rows] == ["100% Pure"]
    assert [s.title for s in repository.searchSongs("fraction").rows] == ["100% Pure"]


def testSearchSongsEscapesWildcards(database):
    _seedSongs(database, [
        _song("s1", "100% Pure"),
        _song("s2", "Under_score"),
        _song("s3", "Plain"),
    ])
    repository = SongRepository(database)
    percent = repository.searchSongs("100%")
    assert [s.title for s in percent.rows] == ["100% Pure"]
    assert percent.total == 1
    # A bare % is a literal, not a wildcard: only the title containing %
    assert [s.title for s in repository.searchSongs("%").rows] == ["100% Pure"]
    # Same for _
    assert [s.title for s in repository.searchSongs("_").rows] == ["Under_score"]


def testSearchSongsEmptyQueryReturnsEmptyNotEverything(database):
    _seedSongs(database, [_song("s1", "One"), _song("s2", "Two")])
    page = SongRepository(database).searchSongs("")
    assert page.rows == []
    assert page.total == 0


def testSearchSongsPagesWithStableOrder(database):
    _seedSongs(database, [
        _song("s1", "Love Beta"),
        _song("s2", "Love Alpha"),
        _song("s3", "Love Gamma"),
        _song("s4", "Other"),
    ])
    repository = SongRepository(database)
    page = repository.searchSongs("love", limit=2)
    assert [s.title for s in page.rows] == ["Love Alpha", "Love Beta"]
    assert page.total == 3
    rest = repository.searchSongs("love", limit=2, offset=2)
    assert [s.title for s in rest.rows] == ["Love Gamma"]
    assert rest.total == 3


def testSearchArtistsMatchesCaseInsensitiveAndEmptyReturnsEmpty(database, artistsPayload):
    repository = ArtistRepository(database)
    repository.upsertArtists([mapArtist(a) for a in artistsPayload["artist"]])
    assert [a.name for a in repository.searchArtists("comedown")] == ["Comedown Kid"]
    assert repository.searchArtists("no such artist") == []
    assert repository.searchArtists("") == []


def testSearchArtistsEscapesWildcards(database):
    repository = ArtistRepository(database)
    repository.upsertArtists([
        mapArtist({"id": "90", "name": "100% Band"}),
        mapArtist({"id": "91", "name": "Plain Band"}),
    ])
    assert [a.name for a in repository.searchArtists("100%")] == ["100% Band"]
    assert [a.name for a in repository.searchArtists("%")] == ["100% Band"]


def testSearchAlbumsMatchesNameAndEmptyReturnsEmpty(database):
    repository = AlbumRepository(database)
    repository.upsertAlbums([
        mapAlbum(_album("1", "Greatest Hits", 2001)),
        mapAlbum(_album("2", "Deep Cuts", 2003)),
    ])
    assert [a.name for a in repository.searchAlbums("greatest")] == ["Greatest Hits"]
    assert repository.searchAlbums("") == []


def testSearchPlaylistsMatchesNameAndEmptyReturnsEmpty(database):
    repository = PlaylistRepository(database)
    repository.upsertPlaylists([
        mapPlaylist({"id": "1", "name": "Road Trip"}),
        mapPlaylist({"id": "2", "name": "Quiet Evening"}),
    ])
    assert [p.name for p in repository.searchPlaylists("road")] == ["Road Trip"]
    assert repository.searchPlaylists("") == []


# --- counts ------------------------------------------------------------------

def testCountsMatchSeededRows(database, artistsPayload):
    _seedSongs(database, [_song("s1", "One"), _song("s2", "Two"), _song("s3", "Three")])
    AlbumRepository(database).upsertAlbums([
        mapAlbum(_album("1", "A", 2000)),
        mapAlbum(_album("2", "B", 2001)),
    ])
    ArtistRepository(database).upsertArtists(
        [mapArtist(a) for a in artistsPayload["artist"]]
    )
    PlaylistRepository(database).upsertPlaylists([mapPlaylist({"id": "1", "name": "P"})])
    assert SongRepository(database).songCount() == 3
    assert AlbumRepository(database).albumCount() == 2
    assert ArtistRepository(database).artistCount() == 4
    assert PlaylistRepository(database).playlistCount() == 1
