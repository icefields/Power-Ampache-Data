"""SQL-only access to SongEntity (PK mediaId — the API `id` goes here).
Never sees HTTP.

Transaction semantics: upserts commit only when this call owns the transaction
(none open on the connection). Inside a caller-owned transaction (AmpacheClient
opens one with BEGIN for multi-repository write-throughs) the commit stays with
the caller so all rows commit as ONE unit."""
from ....domain.Song import Song

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

_SELECT_SQL = (
    "SELECT mediaId, title, albumId, albumName, artistId, artistName, "
    "albumArtist, songUrl, imageUrl, bitrate, streamBitrate, catalog, "
    "channels, composer, filename, genre, mime, playCount, "
    "playlistTrackNumber, rateHz, size, time, trackNumber, year, name, mode, "
    "artists, streamFormat, format, streamMime, publisher, "
    "replayGainTrackGain, replayGainTrackPeak, disk, diskSubtitle, mbId, "
    "comment, language, lyrics, albumMbId, artistMbId, albumArtistMbId, "
    "averageRating, preciseRating, rating FROM SongEntity"
)


def _toSong(row) -> Song:
    # mediaId (the DB PK) surfaces as the clean domain name `id`.
    return Song(
        id=row["mediaId"],
        title=row["title"],
        albumId=row["albumId"],
        albumName=row["albumName"],
        artistId=row["artistId"],
        artistName=row["artistName"],
        albumArtist=row["albumArtist"],
        songUrl=row["songUrl"],
        imageUrl=row["imageUrl"],
        bitrate=row["bitrate"],
        streamBitrate=row["streamBitrate"],
        catalog=row["catalog"],
        channels=row["channels"],
        composer=row["composer"],
        filename=row["filename"],
        genre=row["genre"],
        mime=row["mime"],
        playCount=row["playCount"],
        playlistTrackNumber=row["playlistTrackNumber"],
        rateHz=row["rateHz"],
        size=row["size"],
        time=row["time"],
        trackNumber=row["trackNumber"],
        year=row["year"],
        name=row["name"],
        mode=row["mode"],
        artists=row["artists"],
        streamFormat=row["streamFormat"],
        format=row["format"],
        streamMime=row["streamMime"],
        publisher=row["publisher"],
        replayGainTrackGain=row["replayGainTrackGain"],
        replayGainTrackPeak=row["replayGainTrackPeak"],
        disk=row["disk"],
        diskSubtitle=row["diskSubtitle"],
        mbId=row["mbId"],
        comment=row["comment"],
        language=row["language"],
        lyrics=row["lyrics"],
        albumMbId=row["albumMbId"],
        artistMbId=row["artistMbId"],
        albumArtistMbId=row["albumArtistMbId"],
        averageRating=row["averageRating"],
        preciseRating=row["preciseRating"],
        rating=row["rating"],
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

    def getSongs(self):
        rows = self._database.connection.execute(
            _SELECT_SQL + " ORDER BY searchTitle"
        ).fetchall()
        return [_toSong(row) for row in rows]

    def getSong(self, songId):
        """Read-back for the write-through flow. `songId` is the API id —
        SongEntity's actual PK is mediaId. None if the row is missing — the
        client turns that into an AmpacheError."""
        row = self._database.connection.execute(
            _SELECT_SQL + " WHERE mediaId = ?", (songId,)
        ).fetchone()
        return _toSong(row) if row is not None else None

    def getAlbumSongs(self, albumId):
        """Read-back for the album_songs write-through: the album's songs in
        disk/track order (searchTitle breaks ties)."""
        rows = self._database.connection.execute(
            "SELECT * FROM SongEntity WHERE albumId = ? ORDER BY disk, trackNumber, searchTitle",
            (albumId,),
        ).fetchall()
        return [_toSong(row) for row in rows]

    def getArtistSongs(self, artistId):
        """Read-back for the artist_songs write-through: the artist's songs
        ordered by searchTitle (same DB-derived default as getSongs)."""
        rows = self._database.connection.execute(
            "SELECT * FROM SongEntity WHERE artistId = ? ORDER BY searchTitle",
            (artistId,),
        ).fetchall()
        return [_toSong(row) for row in rows]

    def getSongsByLastPlayed(self, ascending=False):
        """Read-back for the stats recent/forgotten write-throughs: songs with
        play history ordered by HistoryEntity.lastPlayed — DESC (default) =
        recent, most recent first; ASC = forgotten, least recently played
        first — then mediaId for a stable order among ties. Never-played songs
        have no HistoryEntity row and never appear here."""
        order = "ASC" if ascending else "DESC"
        rows = self._database.connection.execute(
            "SELECT song.* FROM SongEntity song JOIN HistoryEntity history "
            "ON history.mediaId = song.mediaId "
            "ORDER BY history.lastPlayed " + order + ", song.mediaId"
        ).fetchall()
        return [_toSong(row) for row in rows]

    def getSongsByPlayCount(self):
        """Read-back for the stats frequent write-through: songs with play
        history ordered by HistoryEntity.playCount DESC (most played first),
        then mediaId for a stable order among ties."""
        rows = self._database.connection.execute(
            "SELECT song.* FROM SongEntity song JOIN HistoryEntity history "
            "ON history.mediaId = song.mediaId "
            "ORDER BY history.playCount DESC, song.mediaId"
        ).fetchall()
        return [_toSong(row) for row in rows]
