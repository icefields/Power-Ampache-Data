"""SQL-only access to ArtistEntity (PK id). Never sees HTTP."""
from ....domain.Artist import Artist

_COLUMNS = (
    "id", "name", "albumCount", "songCount", "genre", "artUrl", "flag",
    "summary", "time", "yearFormed", "placeFormed", "multiUserId", "searchName",
)

_UPSERT_SQL = "INSERT OR REPLACE INTO ArtistEntity ({}) VALUES ({})".format(
    ", ".join(_COLUMNS),
    ", ".join("?" * len(_COLUMNS)),
)

_SELECT_SQL = (
    "SELECT id, name, albumCount, songCount, genre, artUrl, summary, time, "
    "yearFormed, placeFormed FROM ArtistEntity"
)


def _toArtist(row) -> Artist:
    return Artist(
        id=row["id"],
        name=row["name"],
        albumCount=row["albumCount"],
        songCount=row["songCount"],
        genre=row["genre"],
        artUrl=row["artUrl"],
        summary=row["summary"],
        time=row["time"],
        yearFormed=row["yearFormed"],
        placeFormed=row["placeFormed"],
    )


class ArtistRepository:
    def __init__(self, database):
        self._database = database

    def upsertArtists(self, rows) -> None:
        # No transaction here on purpose — the caller owns the commit boundary.
        values = [[row[column] for column in _COLUMNS] for row in rows]
        self._database.connection.executemany(_UPSERT_SQL, values)

    def getArtists(self):
        rows = self._database.connection.execute(
            _SELECT_SQL + " ORDER BY searchName"
        ).fetchall()
        return [_toArtist(row) for row in rows]

    def getArtist(self, artistId):
        """Read-back for the write-through flow. None if the row is missing —
        the client turns that into an AmpacheError."""
        row = self._database.connection.execute(
            _SELECT_SQL + " WHERE id = ?", (artistId,)
        ).fetchone()
        return _toArtist(row) if row is not None else None
