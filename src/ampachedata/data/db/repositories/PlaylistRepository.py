"""SQL-only access to PlaylistEntity (PK id). Never sees HTTP.

Transaction semantics: upserts commit only when this call owns the transaction
(none open on the connection). Inside a caller-owned transaction (AmpacheClient
opens one with BEGIN for multi-repository write-throughs) the commit stays with
the caller so all rows commit as ONE unit."""
from ....domain.Playlist import Playlist
from .LikePattern import likePattern

_COLUMNS = (
    "id", "name", "owner", "items", "type", "artUrl", "flag",
    "preciseRating", "rating", "averageRating", "multiUserId",
)

_UPSERT_SQL = "INSERT OR REPLACE INTO PlaylistEntity ({}) VALUES ({})".format(
    ", ".join(_COLUMNS),
    ", ".join("?" * len(_COLUMNS)),
)

_SELECT_SQL = (
    "SELECT id, name, owner, items, type, artUrl, preciseRating, rating, "
    "averageRating FROM PlaylistEntity"
)


def _toPlaylist(row) -> Playlist:
    return Playlist(
        id=row["id"],
        name=row["name"],
        owner=row["owner"],
        items=row["items"],
        type=row["type"],
        artUrl=row["artUrl"],
        preciseRating=row["preciseRating"],
        rating=row["rating"],
        averageRating=row["averageRating"],
    )


class PlaylistRepository:
    def __init__(self, database):
        self._database = database

    def upsertPlaylists(self, rows) -> None:
        # Commits only when this call owns the transaction (none open yet).
        # Inside a caller-owned transaction the commit stays with the caller so
        # multi-repository write-throughs commit (or roll back) as ONE unit.
        values = [[row[column] for column in _COLUMNS] for row in rows]
        connection = self._database.connection
        ownsTransaction = not connection.in_transaction
        connection.executemany(_UPSERT_SQL, values)
        if ownsTransaction:
            connection.commit()

    def getPlaylists(self):
        """Write-through read-back — identical to listPlaylists (query tier)."""
        return self.listPlaylists()

    def listPlaylists(self):
        """Query tier (DB-only, no network): every cached playlist, ordered
        by name then id. PlaylistEntity has no searchName column and the
        schema is read-only — plain name it is; id breaks ties."""
        rows = self._database.connection.execute(
            _SELECT_SQL + " ORDER BY name, id"
        ).fetchall()
        return [_toPlaylist(row) for row in rows]

    def searchPlaylists(self, query):
        """Query tier (DB-only): substring search over name (no searchName
        column exists on PlaylistEntity). Literal matching (\\, %, _
        escaped; LIKE ? ESCAPE '\\'); SQLite LIKE is case-insensitive for
        ASCII only. Empty query returns []."""
        if not query:
            return []
        pattern = likePattern(query)
        rows = self._database.connection.execute(
            _SELECT_SQL + " WHERE name LIKE ? ESCAPE '\\' ORDER BY name, id",
            (pattern,),
        ).fetchall()
        return [_toPlaylist(row) for row in rows]

    def playlistCount(self) -> int:
        """Query tier: number of cached PlaylistEntity rows (SQL COUNT)."""
        return self._database.connection.execute(
            "SELECT COUNT(*) FROM PlaylistEntity"
        ).fetchone()[0]

    def getPlaylist(self, playlistId):
        """Read-back for the single-playlist write-through flow: the
        PlaylistEntity row with this id, or None."""
        row = self._database.connection.execute(
            _SELECT_SQL + " WHERE id = ?", (playlistId,)
        ).fetchone()
        return _toPlaylist(row) if row is not None else None
