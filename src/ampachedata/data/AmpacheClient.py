"""Public facade. Owns the write-through flow for every read method:

    fetch (Transport) -> map (mappers) -> upsert (repositories) -> read back (repositories)

Repositories are SQL-only and never see HTTP; mappers never see SQL or domain."""
from ..domain.Artist import Artist
from ..domain.PingResult import PingResult
from ..domain.Song import Song
from .ApiMethod import ApiMethod
from .Transport import UrllibTransport
from .auth.SessionManager import ENDPOINT_PATH, SessionManager
from .db.Database import Database
from .db.mappers.AlbumMapper import mapAlbum
from .db.mappers.ArtistMapper import mapArtist
from .db.mappers.HistoryMapper import mapHistory
from .db.mappers.SessionMapper import mapSession
from .db.mappers.SongMapper import mapSong
from .db.repositories.AlbumRepository import AlbumRepository
from .db.repositories.ArtistRepository import ArtistRepository
from .db.repositories.CredentialsRepository import CredentialsRepository
from .db.repositories.HistoryRepository import HistoryRepository
from .db.repositories.SessionRepository import SessionRepository
from .db.repositories.SongRepository import SongRepository
from .errors import AmpacheError, InvalidHandshakeError, raiseForError


class AmpacheClient:
    # Page size for list-method pagination — the single place where default/
    # maximum limit handling lives (CONVENTIONS: Request Building).
    _DEFAULT_PAGE_LIMIT = 500

    def __init__(self, dbPath: str, transport=None):
        self._database = Database(dbPath)
        self._transport = transport if transport is not None else UrllibTransport()
        self._credentialsRepository = CredentialsRepository(self._database)
        self._sessionRepository = SessionRepository(self._database)
        self._sessionManager = SessionManager(
            self._transport, self._sessionRepository, self._credentialsRepository
        )
        self._artistRepository = ArtistRepository(self._database)
        self._albumRepository = AlbumRepository(self._database)
        self._songRepository = SongRepository(self._database)
        self._historyRepository = HistoryRepository(self._database)
        self._lastPayload = None

    @property
    def lastPayload(self):
        """Raw response of the last successful authenticated call (None before
        the first one). Envelope-only fields the write-through flow doesn't
        persist (total_count, md5, ...) are reachable here; entity data still
        comes only from the DB read-back."""
        return self._lastPayload

    def ping(self) -> PingResult:
        """Health check / expiry probe.

        With a session token: extends the session; fresh auth/expiry are persisted
        to SessionEntity BEFORE returning (write-through). Without one: anonymous
        probe returning server/version/compatible only."""
        credentials = self._credentialsRepository.getCredentials()
        if credentials is None:
            raise AmpacheError("no credentials stored in CredentialsEntity; serverUrl unknown")
        session = self._sessionRepository.getSession()
        if session is None or not session.auth:
            payload = self._send(ApiMethod.PING, {}, token=None, serverUrl=credentials.serverUrl)
            raiseForError(payload)
            return PingResult(
                authenticated=False,
                api=payload.get("api") or "",
                server=payload.get("server") or "",
                version=payload.get("version") or "",
                compatible=payload.get("compatible") or "",
            )
        payload = self._sendWithAuth(ApiMethod.PING, {})
        if payload.get("auth") or payload.get("session_expire"):
            self._sessionRepository.upsertSession(mapSession(payload))
        session = self._sessionRepository.getSession()
        return PingResult(
            authenticated=True, auth=session.auth, sessionExpire=session.sessionExpire, api=session.api
        )

    def getArtists(self, filter="", exact=None, add=None, update=None, include=None,
                   albumArtist=None, offset=None, limit=None, cond=None, sort=None):
        """Write-through: fetch -> upsert (one transaction) -> read back ALL artists
        ordered by searchName. The return value comes only from the DB."""
        params = self._listParams(
            filter=filter, exact=exact, add=add, update=update, include=include,
            album_artist=albumArtist, offset=offset, limit=limit, cond=cond, sort=sort,
        )
        artists = self._fetchAllPages(ApiMethod.ARTISTS, params, "artist")
        rows = [mapArtist(artist) for artist in artists]
        self._artistRepository.upsertArtists(rows)
        return self._artistRepository.getArtists()

    def getArtist(self, filter, include=None) -> Artist:
        """Write-through for one artist (UID `filter`; `include` = 'albums'/'songs'
        nests child objects). The artist row plus any nested album/song rows are
        upserted in ONE transaction; the return value is read back from the DB
        only. Partial references inside nested objects (bare {id, name}
        artist/album slots) are extracted onto those rows but never upserted —
        INSERT OR REPLACE would blank their real columns (see the mappers)."""
        params = self._listParams(filter=filter, include=include)
        payload = self._sendWithAuth(ApiMethod.ARTIST, params)
        artistRow = mapArtist(payload)
        albumRows = [mapAlbum(album) for album in payload.get("albums") or []]
        songRows = [mapSong(song) for song in payload.get("songs") or []]
        connection = self._database.connection
        with connection:
            if not connection.in_transaction:
                # BEGIN marks this with-block as the transaction owner: the
                # repositories see the open transaction and leave the commit
                # to this block, so artist + nested rows commit (or roll
                # back) as ONE unit.
                connection.execute("BEGIN")
            self._artistRepository.upsertArtists([artistRow])
            self._albumRepository.upsertAlbums(albumRows)
            self._songRepository.upsertSongs(songRows)
        artist = self._artistRepository.getArtist(artistRow["id"])
        if artist is None:
            raise AmpacheError("artist " + artistRow["id"] + " missing from DB after write-through")
        return artist

    def getAlbumsFromArtist(self, artistId, albumArtist=None, offset=None, limit=None,
                            cond=None, sort=None):
        """artist_albums: write-through for the albums of one artist.

        fetch -> map -> upsert (one transaction, owned by AlbumRepository)
        -> read back from the DB only: WHERE artistId = ? ORDER BY year,
        searchName. Envelope-only fields (total_count, md5) are not persisted;
        reach them via lastPayload. See getAlbumsFromArtist's docstring on the
        repository for the album_artist=0 read-back caveat."""
        params = self._listParams(
            filter=artistId, album_artist=albumArtist, offset=offset,
            limit=limit, cond=cond, sort=sort,
        )
        albums = self._fetchAllPages(ApiMethod.ARTIST_ALBUMS, params, "album")
        rows = [mapAlbum(album) for album in albums]
        self._albumRepository.upsertAlbums(rows)
        return self._albumRepository.getAlbumsFromArtist(artistId)

    def getSongs(self, filter="", exact=None, add=None, update=None, offset=None,
                 limit=None, cond=None, sort=None):
        """songs: write-through for a song list.

        fetch -> map (song rows + HistoryEntity rows for played songs only; null last_played maps to None and is dropped) -> upsert BOTH in
        one transaction -> read back ALL songs ordered by searchTitle. The
        return value comes only from the DB; envelope-only fields
        (total_count, md5) are not persisted — reach them via lastPayload."""
        params = self._listParams(
            filter=filter, exact=exact, add=add, update=update,
            offset=offset, limit=limit, cond=cond, sort=sort,
        )
        songs = self._fetchAllPages(ApiMethod.SONGS, params, "song")
        songRows = [mapSong(song) for song in songs]
        # Never-played songs (null last_played) map to None — drop them so
        # epoch-0 HistoryEntity rows are never written. upsertHistories([])
        # is a no-op (executemany on an empty sequence), so no guard needed.
        historyRows = [row for row in (mapHistory(song) for song in songs) if row is not None]
        connection = self._database.connection
        with connection:
            if not connection.in_transaction:
                # BEGIN makes this with-block the transaction owner (see
                # getArtist): song + history rows commit (or roll back) as
                # ONE unit.
                connection.execute("BEGIN")
            self._songRepository.upsertSongs(songRows)
            self._historyRepository.upsertHistories(historyRows)
        return self._songRepository.getSongs()

    def getSong(self, filter) -> Song:
        """song: write-through for one song (UID `filter`).

        The song row and its HistoryEntity row (playCount; lastPlayed as
        epoch ms) are upserted in ONE transaction; the return value is read
        back from the DB only."""
        params = self._listParams(filter=filter)
        payload = self._sendWithAuth(ApiMethod.SONG, params)
        songRow = mapSong(payload)
        historyRow = mapHistory(payload)
        connection = self._database.connection
        with connection:
            if not connection.in_transaction:
                connection.execute("BEGIN")  # transaction owner — see getArtist
            self._songRepository.upsertSongs([songRow])
            if historyRow is not None:
                # None = never played (null last_played) — no history row.
                self._historyRepository.upsertHistories([historyRow])
        song = self._songRepository.getSong(songRow["mediaId"])
        if song is None:
            raise AmpacheError("song " + songRow["mediaId"] + " missing from DB after write-through")
        return song

    def _fetchAllPages(self, action, params, listKey):
        """The one place list-method pagination lives (CONVENTIONS: implement
        pagination once, reuse everywhere).

        Caller-specified offset/limit: the caller owns the window — the
        request goes out verbatim, once, no auto-pagination.
        No offset/limit: pages of _DEFAULT_PAGE_LIMIT rows are fetched until
        a SHORT page arrives (len(rows) < page limit — the server is out of
        rows; total_count is not trusted on its own) or until offset reaches
        total_count. Rows from every page are collected BEFORE any DB write
        so each list method's write-through stays ONE transaction — no
        partial pages."""
        if "offset" in params or "limit" in params:
            payload = self._sendWithAuth(action, params)
            return payload.get(listKey) or []
        rows = []
        offset = 0
        while True:
            pageParams = dict(params)
            pageParams["offset"] = str(offset)
            pageParams["limit"] = str(self._DEFAULT_PAGE_LIMIT)
            payload = self._sendWithAuth(action, pageParams)
            pageRows = payload.get(listKey) or []
            rows.extend(pageRows)
            offset += len(pageRows)
            if len(pageRows) < self._DEFAULT_PAGE_LIMIT:
                break
            total = int(payload.get("total_count") or 0)
            if total and offset >= total:
                break
        return rows

    def _listParams(self, **params):
        """Single place that builds list-method query params (filter/exact/offset/limit/
        cond/sort/...). None and empty-string values are omitted; everything is
        stringified for the query string. Default/max limit handling lives here."""
        return {key: str(value) for key, value in params.items() if value is not None and value != ""}

    def _sendWithAuth(self, action, params):
        credentials = self._credentialsRepository.getCredentials()
        token = self._sessionManager.ensureSession()
        payload = self._send(action, params, token, credentials.serverUrl)
        try:
            raiseForError(payload)
        except InvalidHandshakeError:
            # 4701: silent re-auth from stored credentials, retry ONCE. goodbye is never called.
            token = self._sessionManager.reauthenticate()
            payload = self._send(action, params, token, credentials.serverUrl)
            raiseForError(payload)
        self._lastPayload = payload
        return payload

    def _send(self, action, params, token, serverUrl):
        url = serverUrl.rstrip("/") + ENDPOINT_PATH
        requestParams = {"action": action.value}
        requestParams.update(params)
        headers = {}
        if token:
            # Session token via Bearer header — NEVER the query string.
            headers["Authorization"] = "Bearer " + token
        return self._transport.send("GET", url, requestParams, headers)
