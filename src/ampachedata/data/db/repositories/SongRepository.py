"""SQL-only access to SongEntity (PK mediaId — the API `id` goes here).
Never sees HTTP.

Transaction semantics: upserts commit only when this call owns the transaction
(none open on the connection). Inside a caller-owned transaction (AmpacheClient
opens one with BEGIN for multi-repository write-throughs) the commit stays with
the caller so all rows commit as ONE unit."""

_COLUMNS = (
    "mediaId", "title", "albumId", "albumName", "artistId", "artistName",
    "albumArtist", "songUrl", "imageUrl", "bitrate", "streamBitrate", "catalog",
    "channels", "composer", "filename", "genre", "mime", "playCount",
    "playlistTrackNumber", "rateHz", "size", "time", "trackNumber", "year",
    "name", "mode", "artists", "flag", "streamFormat", "format", "streamMime",
    "publisher", "replayGainTrackGain", "replayGainTrackPeak", "disk",
    "diskSubtitle", "mbId", "comment", "language", "lyrics", "albumMbId",
    "artistMbId", "albumArtistMbId", "averageRating", "preciseRating", "rating",
    "multiUserId", "searchTitle",
)

_UPSERT_SQL = "INSERT OR REPLACE INTO SongEntity ({}) VALUES ({})".format(
    ", ".join(_COLUMNS),
    ", ".join("?" * len(_COLUMNS)),
)


class SongRepository:
    def __init__(self, database):
        self._database = database

    def upsertSongs(self, rows) -> None:
        # Commits only when this call owns the transaction (none open yet).
        # Inside a caller-owned transaction the commit stays with the caller so
        # multi-repository write-throughs commit (or roll back) as ONE unit.
        values = [[row[column] for column in _COLUMNS] for row in rows]
        connection = self._database.connection
        ownsTransaction = not connection.in_transaction
        connection.executemany(_UPSERT_SQL, values)
        if ownsTransaction:
            connection.commit()
