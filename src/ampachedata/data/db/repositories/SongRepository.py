# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""SQL-only access to SongEntity (PK mediaId — the API `id` goes here).
Never sees HTTP.

Transaction semantics: upserts commit only when this call owns the transaction
(none open on the connection). Inside a caller-owned transaction (AmpacheClient
opens one with BEGIN for multi-repository write-throughs) the commit stays with
the caller so all rows commit as ONE unit."""
from ....domain.PageResult import PageResult
from ....domain.Song import Song
from .LikePattern import likePattern

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
    "averageRating, preciseRating, rating, flag FROM SongEntity"
)

_LIST_FROM = "SELECT song.* FROM SongEntity song"
_LIST_COUNT = "SELECT COUNT(*) FROM SongEntity song"
_RECENT_JOIN = " LEFT JOIN HistoryEntity history ON history.mediaId = song.mediaId"

# Whitelisted ORDER BY clauses for listSongs — the `order` argument is a
# dict key, NEVER interpolated into SQL. Every clause ends in a unique
# tiebreaker so LIMIT/OFFSET windows are stable.
_LIST_ORDERS = {
    "title": " ORDER BY song.searchTitle, song.mediaId",
    "artist": " ORDER BY song.artistName, song.searchTitle, song.mediaId",
    "album": " ORDER BY song.albumName, song.disk, song.trackNumber, song.mediaId",
    "recent": " ORDER BY history.lastPlayed IS NULL, history.lastPlayed DESC, song.mediaId",
}


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
        flag=bool(row["flag"]),
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

    def getPlaylistSongs(self, playlistId):
        """Write-through read-back for playlist_songs — identical to
        playlistSongs (query tier)."""
        return self.playlistSongs(playlistId)

    def playlistSongs(self, playlistId):
        """Query tier (DB-only, no network): the playlist's cached songs
        ordered by PlaylistSongEntity.position ASC — the ordering contract,
        exactly as the payload's playlisttrack gave it — then songId for a
        stable order among ties. Songs removed from the playlist keep their
        join row (upsert-only, no deletion) and still appear here."""
        rows = self._database.connection.execute(
            "SELECT song.* FROM SongEntity song "
            "JOIN PlaylistSongEntity playlistSong "
            "ON playlistSong.songId = song.mediaId "
            "WHERE playlistSong.playlistId = ? "
            "ORDER BY playlistSong.position, playlistSong.songId",
            (playlistId,),
        ).fetchall()
        return [_toSong(row) for row in rows]

    def listSongs(self, order="title", limit=100, offset=0,
                  artistId=None, albumId=None) -> PageResult:
        """Query tier (DB-only, no network): one page of cached songs.

        `order` is whitelisted (a _LIST_ORDERS key, never interpolated):
          "title"  → searchTitle, mediaId
          "artist" → artistName, searchTitle, mediaId
          "album"  → albumName, disk, trackNumber, mediaId
          "recent" → HistoryEntity.lastPlayed DESC via LEFT JOIN; songs
                     without play history sort LAST (the IS NULL expression
                     is 0 for played, 1 for never-played), mediaId tiebreak.
        ORDER BY is mandatory before LIMIT/OFFSET so pages are stable.
        `total` is SQL COUNT over the filtered set — never the server's
        total_count. Raises ValueError for an unknown `order`."""
        if order not in _LIST_ORDERS:
            raise ValueError(
                "unknown song order " + repr(order) +
                " — expected one of: " + ", ".join(sorted(_LIST_ORDERS))
            )
        join = _RECENT_JOIN if order == "recent" else ""
        whereSql, args = self._songFilters(artistId, albumId)
        connection = self._database.connection
        total = connection.execute(_LIST_COUNT + whereSql, args).fetchone()[0]
        rows = connection.execute(
            _LIST_FROM + join + whereSql + _LIST_ORDERS[order] + " LIMIT ? OFFSET ?",
            args + [limit, offset],
        ).fetchall()
        return PageResult(rows=[_toSong(row) for row in rows], total=total)

    def searchSongs(self, query, limit=100, offset=0) -> PageResult:
        """Query tier (DB-only): substring search over song title plus the
        denormalized artistName/albumName columns — no joins, so songs whose
        parent rows aren't cached yet still match.

        The query matches LITERALLY (\\, %, _ escaped; LIKE ? ESCAPE '\\').
        SQLite LIKE is case-insensitive for ASCII only — Cyrillic titles
        match case-sensitively. Empty query returns an empty PageResult,
        never everything. Ordered by searchTitle, mediaId so pages are
        stable. `total` is SQL COUNT over all matches."""
        if not query:
            return PageResult(rows=[], total=0)
        pattern = likePattern(query)
        whereSql = (
            " WHERE (song.title LIKE ? ESCAPE '\\'"
            " OR song.artistName LIKE ? ESCAPE '\\'"
            " OR song.albumName LIKE ? ESCAPE '\\')"
        )
        args = [pattern, pattern, pattern]
        connection = self._database.connection
        total = connection.execute(_LIST_COUNT + whereSql, args).fetchone()[0]
        rows = connection.execute(
            _LIST_FROM + whereSql + _LIST_ORDERS["title"] + " LIMIT ? OFFSET ?",
            args + [limit, offset],
        ).fetchall()
        return PageResult(rows=[_toSong(row) for row in rows], total=total)

    def songCount(self) -> int:
        """Query tier: number of cached SongEntity rows (SQL COUNT)."""
        return self._database.connection.execute(_LIST_COUNT).fetchone()[0]

    @staticmethod
    def _songFilters(artistId, albumId):
        where = []
        args = []
        if artistId is not None:
            where.append("song.artistId = ?")
            args.append(artistId)
        if albumId is not None:
            where.append("song.albumId = ?")
            args.append(albumId)
        return (" WHERE " + " AND ".join(where)) if where else "", args

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
