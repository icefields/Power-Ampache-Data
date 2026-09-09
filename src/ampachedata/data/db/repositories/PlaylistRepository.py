"""SQL-only access to PlaylistEntity (PK id). Never sees HTTP.

Transaction semantics: upserts commit only when this call owns the transaction
(none open on the connection). Inside a caller-owned transaction (AmpacheClient
opens one with BEGIN for multi-repository write-throughs) the commit stays with
the caller so all rows commit as ONE unit."""
from ....domain.Playlist import Playlist

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
        """Read-back for the playlists write-through flow: every PlaylistEntity
        row, ordered by (name, id) — PlaylistEntity has no searchName column,
        so plain name it is; id breaks ties for a stable order."""
        rows = self._database.connection.execute(
            _SELECT_SQL + " ORDER BY name, id"
        ).fetchall()
        return [_toPlaylist(row) for row in rows]

    def getPlaylist(self, playlistId):
        """Read-back for the single-playlist write-through flow: the
        PlaylistEntity row with this id, or None."""
        row = self._database.connection.execute(
            _SELECT_SQL + " WHERE id = ?", (playlistId,)
        ).fetchone()
        return _toPlaylist(row) if row is not None else None
