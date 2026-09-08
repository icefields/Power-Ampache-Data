"""SQL-only access to AlbumEntity (PK id). Never sees HTTP.

Transaction semantics: upserts commit only when this call owns the transaction
(none open on the connection). Inside a caller-owned transaction (AmpacheClient
opens one with BEGIN for multi-repository write-throughs) the commit stays with
the caller so all rows commit as ONE unit."""

_COLUMNS = (
    "id", "name", "basename", "artistId", "artistName", "artists", "time",
    "year", "songCount", "diskCount", "genre", "artUrl", "flag", "rating",
    "averageRating", "multiUserId", "searchName",
)

_UPSERT_SQL = "INSERT OR REPLACE INTO AlbumEntity ({}) VALUES ({})".format(
    ", ".join(_COLUMNS),
    ", ".join("?" * len(_COLUMNS)),
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
