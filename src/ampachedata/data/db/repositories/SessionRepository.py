"""SQL-only access to SessionEntity (single row, PK primaryKey). Never sees HTTP.

Column names are quoted in generated SQL: "update" and "add" are SQLite keywords."""
from ....domain.Session import Session

_COLUMNS = (
    "primaryKey", "add", "albums", "api", "artists", "auth", "catalogs", "clean",
    "genres", "labels", "licenses", "liveStreams", "playlists", "playlistsSearches",
    "podcastEpisodes", "podcasts", "searches", "sessionExpire", "shares", "songs",
    "update", "users", "videos",
)

_COUNT_COLUMNS = (
    "albums", "artists", "catalogs", "genres", "labels", "licenses", "liveStreams",
    "playlists", "playlistsSearches", "podcastEpisodes", "podcasts", "searches",
    "shares", "songs", "users", "videos",
)

_UPSERT_SQL = "INSERT INTO SessionEntity ({}) VALUES ({})".format(
    ", ".join('"{}"'.format(column) for column in _COLUMNS),
    ", ".join("?" * len(_COLUMNS)),
)


class SessionRepository:
    def __init__(self, database):
        self._database = database

    def upsertSession(self, row: dict) -> None:
        # Single-row invariant: DELETE + INSERT in one transaction, so a pre-existing
        # row with a different PK value can never cause a second row.
        values = [row[column] for column in _COLUMNS]
        with self._database.connection:
            self._database.connection.execute("DELETE FROM SessionEntity")
            self._database.connection.execute(_UPSERT_SQL, values)

    def clearSession(self) -> None:
        """Delete the single session row (goodbye teardown). CredentialsEntity is
        never touched — stored credentials survive so a new client can re-handshake."""
        with self._database.connection:
            self._database.connection.execute("DELETE FROM SessionEntity")

    def getSession(self):
        row = self._database.connection.execute(
            "SELECT * FROM SessionEntity LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Session(
            auth=row["auth"],
            sessionExpire=row["sessionExpire"],
            api=row["api"],
            counts={column: row[column] for column in _COUNT_COLUMNS},
        )
