"""SQL-only access to AlbumEntity (PK id). Never sees HTTP.

Transaction semantics: upserts commit only when this call owns the transaction
(none open on the connection). Inside a caller-owned transaction (AmpacheClient
opens one with BEGIN for multi-repository write-throughs) the commit stays with
the caller so all rows commit as ONE unit."""
from ....domain.Album import Album

_COLUMNS = (
    "id", "name", "basename", "artistId", "artistName", "artists", "time",
    "year", "songCount", "diskCount", "genre", "artUrl", "flag", "rating",
    "averageRating", "multiUserId", "searchName",
)

_UPSERT_SQL = "INSERT OR REPLACE INTO AlbumEntity ({}) VALUES ({})".format(
    ", ".join(_COLUMNS),
    ", ".join("?" * len(_COLUMNS)),
)

_SELECT_SQL = (
    "SELECT id, name, basename, artistId, artistName, artists, time, year, "
    "songCount, diskCount, genre, artUrl, rating, averageRating FROM AlbumEntity"
)


def _toAlbum(row) -> Album:
    return Album(
        id=row["id"],
        name=row["name"],
        basename=row["basename"],
        artistId=row["artistId"],
        artistName=row["artistName"],
        artists=row["artists"],
        time=row["time"],
        year=row["year"],
        songCount=row["songCount"],
        diskCount=row["diskCount"],
        genre=row["genre"],
        artUrl=row["artUrl"],
        rating=row["rating"],
        averageRating=row["averageRating"],
    )


class AlbumRepository:
    def __init__(self, database):
        self._database = database

    def upsertAlbums(self, rows) -> None:
        # Commits only when this call owns the transaction (none open yet).
        # Inside a caller-owned transaction the commit stays with the caller so
        # multi-repository write-throughs commit (or roll back) as ONE unit.
        values = [[row[column] for column in _COLUMNS] for row in rows]
        connection = self._database.connection
        ownsTransaction = not connection.in_transaction
        connection.executemany(_UPSERT_SQL, values)
        if ownsTransaction:
            connection.commit()

    def getAlbumsFromArtist(self, artistId):
        """Read-back for the write-through flow: every AlbumEntity row whose
        album-artist reference is artistId, ordered by year then searchName
        (DB-derived ordering). Caveat: with album_artist=0 the server may
        return albums where the artist is only a SONG artist; those rows are
        still persisted, but this read-back keys on the album-artist
        reference, so they are not returned here."""
        rows = self._database.connection.execute(
            _SELECT_SQL + " WHERE artistId = ? ORDER BY year, searchName", (artistId,)
        ).fetchall()
        return [_toAlbum(row) for row in rows]

    def getAlbums(self):
        """Read-back for the albums write-through flow: every AlbumEntity row,
        ordered by year then searchName (DB-derived ordering)."""
        rows = self._database.connection.execute(
            _SELECT_SQL + " ORDER BY year, searchName"
        ).fetchall()
        return [_toAlbum(row) for row in rows]

    def getAlbum(self, albumId):
        """Read-back for the single-album write-through flow: the AlbumEntity
        row with this id, or None."""
        row = self._database.connection.execute(
            _SELECT_SQL + " WHERE id = ?", (albumId,)
        ).fetchone()
        return _toAlbum(row) if row is not None else None
