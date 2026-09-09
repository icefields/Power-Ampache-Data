"""SQL-only access to ArtistEntity (PK id). Never sees HTTP.

Transaction semantics: upserts commit only when this call owns the transaction
(none open on the connection). Inside a caller-owned transaction (AmpacheClient
opens one with BEGIN for multi-repository write-throughs) the commit stays with
the caller so all rows commit as ONE unit."""
from ....domain.Artist import Artist
from .LikePattern import likePattern

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
    "yearFormed, placeFormed, flag FROM ArtistEntity"
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
        flag=bool(row["flag"]),
    )


class ArtistRepository:
    def __init__(self, database):
        self._database = database

    def upsertArtists(self, rows) -> None:
        # Commits only when this call owns the transaction (none open yet).
        # Inside a caller-owned transaction the commit stays with the caller so
        # multi-repository write-throughs commit (or roll back) as ONE unit.
        values = [[row[column] for column in _COLUMNS] for row in rows]
        connection = self._database.connection
        ownsTransaction = not connection.in_transaction
        connection.executemany(_UPSERT_SQL, values)
        if ownsTransaction:
            connection.commit()

    def getArtists(self):
        """Write-through read-back — identical to listArtists (query tier)."""
        return self.listArtists()

    def listArtists(self):
        """Query tier (DB-only, no network): every cached artist, ordered by
        searchName then id (stable)."""
        rows = self._database.connection.execute(
            _SELECT_SQL + " ORDER BY searchName, id"
        ).fetchall()
        return [_toArtist(row) for row in rows]

    def searchArtists(self, query):
        """Query tier (DB-only): substring search over name and searchName.
        Literal matching (\\, %, _ escaped; LIKE ? ESCAPE '\\'); SQLite LIKE
        is case-insensitive for ASCII only. Empty query returns []."""
        if not query:
            return []
        pattern = likePattern(query)
        rows = self._database.connection.execute(
            _SELECT_SQL
            + " WHERE (name LIKE ? ESCAPE '\\' OR searchName LIKE ? ESCAPE '\\')"
            " ORDER BY searchName, id",
            (pattern, pattern),
        ).fetchall()
        return [_toArtist(row) for row in rows]

    def artistCount(self) -> int:
        """Query tier: number of cached ArtistEntity rows (SQL COUNT)."""
        return self._database.connection.execute(
            "SELECT COUNT(*) FROM ArtistEntity"
        ).fetchone()[0]

    def getArtist(self, artistId):
        """Read-back for the write-through flow. None if the row is missing —
        the client turns that into an AmpacheError."""
        row = self._database.connection.execute(
            _SELECT_SQL + " WHERE id = ?", (artistId,)
        ).fetchone()
        return _toArtist(row) if row is not None else None
