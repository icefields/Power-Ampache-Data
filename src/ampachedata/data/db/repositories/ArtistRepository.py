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


class ArtistRepository:
    def __init__(self, database):
        self._database = database

    def upsertArtists(self, rows) -> None:
        # One transaction for the whole list: all rows committed before any read-back.
        values = [[row[column] for column in _COLUMNS] for row in rows]
        with self._database.connection:
            self._database.connection.executemany(_UPSERT_SQL, values)

    def getArtists(self):
        rows = self._database.connection.execute(
            "SELECT id, name, albumCount, songCount, genre, artUrl, summary, time, "
            "yearFormed, placeFormed FROM ArtistEntity ORDER BY searchName"
        ).fetchall()
        return [
            Artist(
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
            for row in rows
        ]
