"""Public facade. Owns the write-through flow for every read method:

    fetch (Transport) -> map (mappers) -> upsert (repositories) -> read back (repositories)

Repositories are SQL-only and never see HTTP; mappers never see SQL or domain."""
from ..domain.Artist import Artist
from ..domain.PingResult import PingResult
from .ApiMethod import ApiMethod
from .Transport import UrllibTransport
from .auth.SessionManager import ENDPOINT_PATH, SessionManager
from .db.Database import Database
from .db.mappers.AlbumMapper import mapAlbum
from .db.mappers.ArtistMapper import mapArtist
from .db.mappers.SessionMapper import mapSession
from .db.mappers.SongMapper import mapSong
from .db.repositories.AlbumRepository import AlbumRepository
from .db.repositories.ArtistRepository import ArtistRepository
from .db.repositories.CredentialsRepository import CredentialsRepository
from .db.repositories.SessionRepository import SessionRepository
from .db.repositories.SongRepository import SongRepository
from .errors import AmpacheError, InvalidHandshakeError, raiseForError


class AmpacheClient:
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
        payload = self._sendWithAuth(ApiMethod.ARTISTS, params)
        rows = [mapArtist(artist) for artist in payload.get("artist") or []]
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
