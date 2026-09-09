"""Live smoke check against a real Ampache server — NOT a unit test.

pytest never collects this file (pyproject testpaths = tests/); run it by
hand against a musicdb.db that already holds credentials. Everything the
client needs (username, password hash, serverUrl) comes from the DB — the
script takes only the DB path, never a secret:

    python scripts/live_check.py /path/to/musicdb.db

Requires the package installed (pip install -e .); no sys.path hacks."""
import sqlite3
import sys
from datetime import datetime, timezone
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit

from ampachedata import AmpacheClient, InvalidHandshakeError
from ampachedata.data.db.Database import Database
from ampachedata.data.db.repositories.SessionRepository import SessionRepository

USAGE = "usage: python scripts/live_check.py [--keep-session] <path-to-musicdb.db>"
ARTIST_LIMIT = 50
READ_CAP = 200 * 1024  # ~200KB — abort body reads past this
# Media-step song id — HARDCODED, never picked dynamically: live-verified
# streaming via mpv on 2026-09-09. Ids 180831 and 215751 have broken backing
# files server-side and hang the fetches.
MEDIA_SONG_ID = "224408"
_TABLES = ("ArtistEntity", "AlbumEntity", "SongEntity", "HistoryEntity")


def _counts(dbPath):
    connection = sqlite3.connect(dbPath)
    try:
        return {
            table: connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            for table in _TABLES
        }
    finally:
        connection.close()


def _historyIds(dbPath):
    connection = sqlite3.connect(dbPath)
    try:
        return {
            row[0]
            for row in connection.execute("SELECT id FROM HistoryEntity").fetchall()
        }
    finally:
        connection.close()


def _fetchRange(url):
    """GET url with 'Range: bytes=0-1024'. Returns (ok, status, contentType,
    bytesReceived); ok means HTTP 200 or 206. Reads at most READ_CAP bytes then
    closes — a 200 response ignores Range and streams the whole file, so the
    cap is what aborts the body instead of downloading it."""
    request = urllib.request.Request(url, headers={"Range": "bytes=0-1024"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            contentType = response.headers.get("Content-Type") or "<none>"
            data = response.read(READ_CAP)
            return status in (200, 206), status, contentType, len(data)
    except urllib.error.HTTPError as error:
        return False, error.code, error.headers.get("Content-Type") or "<none>", 0
    except Exception as error:
        print("    fetch failed: %r" % (error,))
        return False, 0, "<none>", 0


def _checkMediaUrl(url, action, liveToken, songId):
    """Printed string assertions: the URL must carry these exact fragments.
    Returns True only if every one is present."""
    allOk = True
    for fragment in ("action=" + action, liveToken, "filter=" + songId, "type=song", "stats=0"):
        ok = fragment in url
        allOk = allOk and ok
        label = "auth=<live token>" if fragment == liveToken else fragment
        print("    %s URL contains %-22s %s" % (action, label, "yes" if ok else "NO"))
    return allOk


def _report(results):
    allOk = True
    for label, ok in results:
        allOk = allOk and ok
        print(("PASS" if ok else "FAIL") + " " + label)
    return allOk


def main(argv):
    args = argv[1:]
    keepSession = "--keep-session" in args
    args = [arg for arg in args if arg != "--keep-session"]
    if len(args) != 1:
        print(USAGE)
        return 2
    dbPath = args[0]
    results = []

    before = _counts(dbPath)
    print("scratch DB: " + dbPath)
    print("row counts before: " + str(before))

    client = AmpacheClient(dbPath=dbPath)

    # --- Step 1: getArtists (triggers the silent handshake), then ping ------------
    # Order matters: ping works unauthenticated per the spec, so on a cold cache
    # (no session yet) it would correctly report authenticated=False. getArtists
    # is authenticated — it triggers the handshake from the stored key — so the
    # ping AFTER it proves the persisted session token.
    print("\n[1] getArtists(limit=%d) + ping" % ARTIST_LIMIT)
    artists = client.getArtists(limit=ARTIST_LIMIT)
    totalCount = (client.lastPayload or {}).get("total_count")
    print("    returned: %d artist(s), envelope total_count: %s" % (len(artists), totalCount))
    if artists:
        print("    first by searchName: %s (id %s)" % (artists[0].name, artists[0].id))
        print("    last  by searchName: %s (id %s)" % (artists[-1].name, artists[-1].id))
    ping = client.ping()
    print("    ping: authenticated=" + str(ping.authenticated) + " api=" + str(ping.api))
    results.append(("ping authenticated", ping.authenticated))
    results.append(("getArtists returned rows", len(artists) > 0))

    # --- Step 2: getArtist with include -------------------------------------------
    print("\n[2] getArtist(id, include=albums,songs)")
    if not artists:
        print("    skipped — no artist to pick")
        results.append(("getArtist include", False))
        artist = None
    else:
        picked = artists[0].id
        print("    picked artist id %s" % picked)
        artist = client.getArtist(picked, include="albums,songs")
        mid = _counts(dbPath)
        albumsAdded = mid["AlbumEntity"] - before["AlbumEntity"]
        songsAdded = mid["SongEntity"] - before["SongEntity"]
        print("    artist: %s" % artist.name)
        print("    nested upserted: %d album row(s), %d song row(s)" % (albumsAdded, songsAdded))
        results.append(("getArtist returned the requested artist", artist.id == picked))
        results.append(("include upserted nested rows", albumsAdded > 0 or songsAdded > 0))

    # --- Step 3: write-through verification (direct DB reads) ---------------------
    print("\n[3] write-through verification (direct DB reads)")
    after = _counts(dbPath)
    print("    row counts after: " + str(after))
    # The scratch DB is pre-populated: upserts of existing artists correctly leave
    # the ArtistEntity count unchanged, so presence — not count growth — is the check.
    sample = artists[:3] + artists[-2:] if len(artists) > 5 else artists
    sampleIds = [a.id for a in sample]
    connection = sqlite3.connect(dbPath)
    try:
        found = {
            row[0]
            for row in connection.execute(
                "SELECT id FROM ArtistEntity WHERE id IN (%s)"
                % ",".join("?" * len(sampleIds)),
                sampleIds,
            )
        } if sampleIds else set()
    finally:
        connection.close()
    missing = [a.id for a in sample if a.id not in found]
    print("    sampled %d artist id(s): %s" % (len(sampleIds), ", ".join(sampleIds) or "<none>"))
    print("    missing from ArtistEntity: %s" % (", ".join(missing) if missing else "none"))
    results.append(("fetched artists present in DB", bool(sampleIds) and not missing))
    if artist is not None:
        connection = sqlite3.connect(dbPath)
        try:
            artistRow = connection.execute(
                "SELECT name FROM ArtistEntity WHERE id = ?", (artist.id,)
            ).fetchone()
            albumRows = connection.execute(
                "SELECT COUNT(*) FROM AlbumEntity WHERE artistId = ?", (artist.id,)
            ).fetchone()[0]
            songRows = connection.execute(
                "SELECT COUNT(*) FROM SongEntity WHERE artistId = ?", (artist.id,)
            ).fetchone()[0]
        finally:
            connection.close()
        print("    include-artist row in DB: %s" % (artistRow[0] if artistRow else "<missing>"))
        print("    include-artist album rows: %d, song rows: %d" % (albumRows, songRows))
        results.append(("include-artist persisted", artistRow is not None))
        results.append(
            ("include-artist album/song rows present", albumRows > 0 or songRows > 0)
        )

    # --- Step 4: getAlbumsFromArtist ----------------------------------------------
    print("\n[4] getAlbumsFromArtist(artistId)")
    if artist is None:
        print("    skipped — no include-artist to pick")
        results.append(("getAlbumsFromArtist", False))
    else:
        picked = artist.id
        print("    picked artist id %s (%s)" % (picked, artist.name))
        albums = client.getAlbumsFromArtist(picked)
        totalCount = (client.lastPayload or {}).get("total_count")
        print("    returned: %d album(s), envelope total_count: %s" % (len(albums), totalCount))
        if albums:
            print("    first by (year, searchName): %s (%s, id %s)"
                  % (albums[0].name, albums[0].year, albums[0].id))
            print("    last  by (year, searchName): %s (%s, id %s)"
                  % (albums[-1].name, albums[-1].year, albums[-1].id))
        # Presence-based, NOT count growth: the scratch DB is pre-populated, so
        # upserts of existing albums correctly leave the count unchanged.
        connection = sqlite3.connect(dbPath)
        try:
            albumRows = connection.execute(
                "SELECT name FROM AlbumEntity WHERE artistId = ?", (picked,)
            ).fetchall()
        finally:
            connection.close()
        print("    AlbumEntity rows with artistId=%s: %d" % (picked, len(albumRows)))
        if albumRows:
            print("    sample album in DB: %s" % albumRows[0][0])
        results.append(("getAlbumsFromArtist returned rows", len(albums) > 0))
        results.append(("album rows present in DB for artist", len(albumRows) > 0))

    # --- Step 4b: getSong + getSongs (narrow filter) ------------------------------
    print("\n[4b] getSong + getSongs (narrow filter)")
    if artist is None:
        print("    skipped — no include-artist to pick songs from")
        results.append(("getSong", False))
        results.append(("getSongs", False))
    else:
        connection = sqlite3.connect(dbPath)
        try:
            songRow = connection.execute(
                "SELECT mediaId, title FROM SongEntity WHERE artistId = ? LIMIT 1",
                (artist.id,),
            ).fetchone()
        finally:
            connection.close()
        if songRow is None:
            print("    skipped — include-artist has no song rows in the DB")
            results.append(("getSong", False))
            results.append(("getSongs", False))
        else:
            songId, songTitle = songRow
            print("    picked song id %s (%s)" % (songId, songTitle))

            # getSong: single fetch, write-through, read-back by mediaId.
            song = client.getSong(songId)
            print("    getSong: %s (mediaId %s)" % (song.title, song.id))
            results.append(("getSong returned the requested song", song.id == songId))

            # getSongs: NARROW on purpose — an exact title match keeps the
            # pagination loop to one page. NEVER call it unfiltered here:
            # that would paginate the entire server library.
            songs = client.getSongs(filter=songTitle, exact=1)
            totalCount = (client.lastPayload or {}).get("total_count")
            print("    getSongs(filter=%r, exact=1): %d returned, envelope total_count: %s"
                  % (songTitle, len(songs), totalCount))
            if songs:
                print("    first by searchTitle: %s (id %s)" % (songs[0].title, songs[0].id))
                print("    last  by searchTitle: %s (id %s)" % (songs[-1].title, songs[-1].id))
            results.append(("getSongs returned rows", len(songs) > 0))

            # Presence-based verification, never count growth (pre-populated DB).
            connection = sqlite3.connect(dbPath)
            try:
                persisted = connection.execute(
                    "SELECT title FROM SongEntity WHERE mediaId = ?", (songId,)
                ).fetchone()
                historyRow = connection.execute(
                    "SELECT id, playCount, lastPlayed FROM HistoryEntity WHERE mediaId = ?",
                    (songId,),
                ).fetchone()
            finally:
                connection.close()
            print("    SongEntity row for mediaId %s: %s"
                  % (songId, persisted[0] if persisted else "<missing>"))
            results.append(
                ("getSong persisted with matching title",
                 persisted is not None and persisted[0] == songTitle)
            )

            # History: the epoch-ms conversion's first contact with real data.
            # A null last_played legitimately means no row — both outcomes pass.
            if historyRow is not None:
                historyId, playCount, lastPlayed = historyRow
                iso = datetime.fromtimestamp(lastPlayed / 1000, tz=timezone.utc).isoformat()
                print("    HistoryEntity row: id=%s playCount=%d lastPlayed=%d (%s)"
                      % (historyId, playCount, lastPlayed, iso))
            else:
                print("    no history row (null last_played)")

    # --- Step 4c: getAlbums (narrow filter) + getAlbum -----------------------------
    print("\n[4c] getAlbums (narrow filter) + getAlbum")
    if not albums:
        print("    skipped — no album to pick")
        results.append(("getAlbums", False))
        results.append(("getAlbum", False))
    else:
        pickedAlbum = albums[0]
        print("    picked album id %s (%s)" % (pickedAlbum.id, pickedAlbum.name))

        # getAlbums: NARROW on purpose — an exact name match keeps the
        # auto-pagination loop to a single page (short page < page limit).
        # NEVER call it unfiltered here: that would paginate the entire
        # server library.
        filtered = client.getAlbums(filter=pickedAlbum.name, exact=1)
        totalCount = (client.lastPayload or {}).get("total_count")
        print("    getAlbums(filter=%r, exact=1): %d returned, envelope total_count: %s"
              % (pickedAlbum.name, len(filtered), totalCount))
        if filtered:
            print("    first by (year, searchName): %s (%s, id %s)"
                  % (filtered[0].name, filtered[0].year, filtered[0].id))
        results.append(("getAlbums returned rows", len(filtered) > 0))

        # getAlbum: single fetch, write-through, read-back by id.
        album = client.getAlbum(pickedAlbum.id)
        print("    getAlbum: %s (year %s, songCount %d)"
              % (album.name, album.year, album.songCount))
        results.append(("getAlbum returned the requested album", album.id == pickedAlbum.id))

        # Presence-based verification, never count growth (pre-populated DB).
        connection = sqlite3.connect(dbPath)
        try:
            persisted = connection.execute(
                "SELECT name FROM AlbumEntity WHERE id = ?", (pickedAlbum.id,)
            ).fetchone()
        finally:
            connection.close()
        print("    AlbumEntity row for id %s: %s"
              % (pickedAlbum.id, persisted[0] if persisted else "<missing>"))
        results.append(
            ("getAlbum persisted with matching name",
             persisted is not None and persisted[0] == pickedAlbum.name)
        )

    # --- Step 4d: getAlbumSongs + getArtistSongs (scoped song lists) --------------
    print("\n[4d] getAlbumSongs + getArtistSongs (scoped song lists)")
    if not albums:
        print("    skipped — no album to pick")
        results.append(("getAlbumSongs", False))
        results.append(("getArtistSongs", False))
    else:
        # Pick the album with the most songs — never a fixed id.
        pickedAlbum = max(albums, key=lambda album: album.songCount)
        print("    picked album id %s (%s, songCount %d)"
              % (pickedAlbum.id, pickedAlbum.name, pickedAlbum.songCount))

        # getAlbumSongs: read-back is DB-derived — disk, trackNumber, searchTitle.
        albumSongs = client.getAlbumSongs(pickedAlbum.id)
        totalCount = (client.lastPayload or {}).get("total_count")
        print("    getAlbumSongs(%s): %d returned, envelope total_count: %s"
              % (pickedAlbum.id, len(albumSongs), totalCount))
        for song in albumSongs[:3]:
            print("    first: disk %d track %d — %s" % (song.disk, song.trackNumber, song.title))
        if len(albumSongs) > 3:
            last = albumSongs[-1]
            print("    last:  disk %d track %d — %s" % (last.disk, last.trackNumber, last.title))
        results.append(("getAlbumSongs returned rows", len(albumSongs) > 0))

        # getArtistSongs: same artist, read-back ordered by searchTitle.
        artistSongs = client.getArtistSongs(picked)
        totalCount = (client.lastPayload or {}).get("total_count")
        print("    getArtistSongs(%s): %d returned, envelope total_count: %s"
              % (picked, len(artistSongs), totalCount))
        if artistSongs:
            print("    first by searchTitle: %s (id %s)" % (artistSongs[0].title, artistSongs[0].id))
            print("    last  by searchTitle: %s (id %s)" % (artistSongs[-1].title, artistSongs[-1].id))
        results.append(("getArtistSongs returned rows", len(artistSongs) > 0))

        # Presence-based verification, never count growth (pre-populated DB):
        # the album's songs exist in SongEntity with matching albumId.
        connection = sqlite3.connect(dbPath)
        try:
            albumSongRows = connection.execute(
                "SELECT title, trackNumber FROM SongEntity WHERE albumId = ? ORDER BY disk, trackNumber",
                (pickedAlbum.id,),
            ).fetchall()
        finally:
            connection.close()
        print("    SongEntity rows with albumId=%s: %d" % (pickedAlbum.id, len(albumSongRows)))
        if albumSongRows:
            print("    example in DB: %s (track %d)" % (albumSongRows[0][0], albumSongRows[0][1]))
        results.append(("album songs present in DB with matching albumId", len(albumSongRows) > 0))

    # --- Step 4e: getRecentSongs (stats, filter=recent) ----------------------------
    print("\n[4e] getRecentSongs() — stats filter=recent, no limit")
    recentSongs = client.getRecentSongs()
    totalCount = (client.lastPayload or {}).get("total_count")
    print("    returned: %d song(s), envelope total_count: %s" % (len(recentSongs), totalCount))

    # lastPlayed is NOT on Song — it lives on HistoryEntity (which also drives
    # the read-back ordering). Load it keyed by mediaId for the printout.
    connection = sqlite3.connect(dbPath)
    try:
        historyByMediaId = {
            row[0]: (row[1], row[2])
            for row in connection.execute(
                "SELECT mediaId, playCount, lastPlayed FROM HistoryEntity"
            ).fetchall()
        }
    finally:
        connection.close()

    def _printRecent(song):
        playCount, lastPlayed = historyByMediaId.get(song.id, (song.playCount, 0))
        iso = datetime.fromtimestamp(lastPlayed / 1000, tz=timezone.utc).isoformat()
        print("    %s — playCount %d, lastPlayed %d (%s)"
              % (song.title, playCount, lastPlayed, iso))

    # Read-back is HistoryEntity-derived: lastPlayed DESC, most recent first.
    for song in recentSongs[:3]:
        _printRecent(song)
    if len(recentSongs) > 3:
        _printRecent(recentSongs[-1])

    # Presence-based verification, never count growth (pre-populated DB).
    missing = [song.id for song in recentSongs if song.id not in historyByMediaId]
    print("    returned songs missing a HistoryEntity row: %s"
          % (", ".join(missing) if missing else "none"))
    if recentSongs:
        exampleId = recentSongs[0].id
        playCount, lastPlayed = historyByMediaId[exampleId]
        iso = datetime.fromtimestamp(lastPlayed / 1000, tz=timezone.utc).isoformat()
        print("    example HistoryEntity row: mediaId=%s playCount=%d lastPlayed=%d (%s)"
              % (exampleId, playCount, lastPlayed, iso))
    results.append(("getRecentSongs returned rows", len(recentSongs) > 0))
    results.append(("recent songs have HistoryEntity rows", bool(recentSongs) and not missing))

    # --- Step 4f: getRecentAlbums (stats, type=album, filter=recent) ---------------
    print("\n[4f] getRecentAlbums() — stats type=album filter=recent, no limit")
    recentAlbums = client.getRecentAlbums()
    totalCount = (client.lastPayload or {}).get("total_count")
    print("    returned: %d album(s), envelope total_count: %s" % (len(recentAlbums), totalCount))

    # Read-back is searchName-ordered (AlbumEntity has no play columns — the
    # documented stats-album limitation), NOT by recency.
    for album in recentAlbums[:3]:
        print("    %s (%s, %d song(s))" % (album.name, album.year, album.songCount))
    if len(recentAlbums) > 3:
        last = recentAlbums[-1]
        print("    last: %s (%s, %d song(s))" % (last.name, last.year, last.songCount))

    # Presence-based verification, never count growth (pre-populated DB).
    albumIds = [album.id for album in recentAlbums]
    connection = sqlite3.connect(dbPath)
    try:
        found = {
            row[0]
            for row in connection.execute(
                "SELECT id FROM AlbumEntity WHERE id IN (%s)"
                % ",".join("?" * len(albumIds)),
                albumIds,
            )
        } if albumIds else set()
        exampleRow = connection.execute(
            "SELECT name, year FROM AlbumEntity WHERE id = ?",
            (recentAlbums[0].id,),
        ).fetchone() if recentAlbums else None
    finally:
        connection.close()
    missing = [album.id for album in recentAlbums if album.id not in found]
    print("    returned albums missing from AlbumEntity: %s"
          % (", ".join(missing) if missing else "none"))
    if exampleRow is not None:
        print("    example AlbumEntity row: %s (%s)" % (exampleRow[0], exampleRow[1]))
    results.append(("getRecentAlbums returned rows", len(recentAlbums) > 0))
    results.append(("recent albums present in AlbumEntity", bool(recentAlbums) and not missing))

    # --- Step 4g: stats newest/highest (song + album) ------------------------------
    print("\n[4g] stats newest/highest — getNewestSongs, getHighestSongs, getNewestAlbums, getHighestAlbums")
    historyIdsBefore = _historyIds(dbPath)

    def _presenceCheck(table, idColumn, ids):
        """Every returned id present in the DB (read-back verification)."""
        if not ids:
            return False
        connection = sqlite3.connect(dbPath)
        try:
            found = {
                row[0]
                for row in connection.execute(
                    "SELECT " + idColumn + " FROM " + table + " WHERE " + idColumn
                    + " IN (%s)" % ",".join("?" * len(ids)),
                    ids,
                )
            }
        finally:
            connection.close()
        missing = [i for i in ids if i not in found]
        if missing:
            print("    missing from %s: %s" % (table, ", ".join(missing)))
        return not missing

    def _runStatsMethod(label, method, table, idColumn):
        """Call one stats method, print count vs envelope total_count, presence-check."""
        entities = method()
        totalCount = (client.lastPayload or {}).get("total_count")
        print("    %s: %d returned, envelope total_count: %s" % (label, len(entities), totalCount))
        uniqueIds = len({e.id for e in entities})
        print("    %s: %d rows, %d unique ids%s"
              % (label, len(entities), uniqueIds,
                 " — DUPLICATES" if uniqueIds < len(entities) else ""))
        if entities:
            print("    first: %s (id %s)" % (entities[0].name if hasattr(entities[0], "name") else entities[0].title, entities[0].id))
            print("    last:  %s (id %s)" % (entities[-1].name if hasattr(entities[-1], "name") else entities[-1].title, entities[-1].id))
        ids = [e.id for e in entities]
        present = _presenceCheck(table, idColumn, ids)
        results.append((label + " returned rows", len(entities) > 0))
        results.append((label + " all present in " + table, present))
        return entities, ids

    _, newestSongIds = _runStatsMethod("getNewestSongs", client.getNewestSongs, "SongEntity", "mediaId")
    _, highestSongIds = _runStatsMethod("getHighestSongs", client.getHighestSongs, "SongEntity", "mediaId")
    newestRows, _ = _runStatsMethod("getNewestAlbums", client.getNewestAlbums, "AlbumEntity", "id")
    highestRows, _ = _runStatsMethod("getHighestAlbums", client.getHighestAlbums, "AlbumEntity", "id")

    # Overlap of the two RETURNED lists, captured at call time above — never
    # re-fetched: both read back the whole AlbumEntity table, so a re-fetch
    # after the highest upsert would compare the table against itself.
    # Near-total overlap means the server ignores the filter.
    newestAlbumIds = {album.id for album in newestRows}
    highestAlbumIds = {album.id for album in highestRows}
    overlap = len(newestAlbumIds & highestAlbumIds)
    print("    album overlap: %d of %d newest ids also in highest"
          % (overlap, len(newestAlbumIds)))

    # Newest/highest are not play-based stats, but the shared write-through
    # still persists history rows for fetched songs that carry non-null
    # last_played (same as getSongs). Growth is legitimate — the check is
    # provenance: every NEW history row's mediaId must be a song fetched in
    # this step (the payload's play data is the only possible source).
    historyIdsAfter = _historyIds(dbPath)
    newHistoryIds = historyIdsAfter - historyIdsBefore
    fetchedSongIds = set(newestSongIds) | set(highestSongIds)
    connection = sqlite3.connect(dbPath)
    try:
        newHistoryMediaIds = {
            row[0]
            for row in connection.execute(
                "SELECT mediaId FROM HistoryEntity WHERE id IN (%s)"
                % ",".join("?" * len(newHistoryIds)),
                list(newHistoryIds),
            )
        } if newHistoryIds else set()
    finally:
        connection.close()
    unsourced = newHistoryMediaIds - fetchedSongIds
    print("    history rows before/after: %d / %d (%d new)"
          % (len(historyIdsBefore), len(historyIdsAfter), len(newHistoryIds)))
    print("    new history mediaIds not among fetched songs: %s"
          % (", ".join(sorted(unsourced)) if unsourced else "none"))
    results.append(("stats newest/highest history writes all sourced from payload play data",
                    not unsourced))

    # --- Step 4h: playlists tier — getPlaylists, getPlaylist, getSongsFromPlaylist ---
    print("\n[4h] playlists tier — getPlaylists, getPlaylist, getSongsFromPlaylist")
    historyIdsBefore = _historyIds(dbPath)

    # getPlaylists: no offset/limit -> auto-paginates EVERY playlist. Unlike
    # the song library, playlists are few and bounded — a full fetch is cheap.
    playlists = client.getPlaylists()
    totalCount = (client.lastPayload or {}).get("total_count")
    print("    getPlaylists: %d returned, envelope total_count: %s" % (len(playlists), totalCount))
    uniqueIds = len({playlist.id for playlist in playlists})
    print("    getPlaylists: %d rows, %d unique ids%s"
          % (len(playlists), uniqueIds,
             " — DUPLICATES" if uniqueIds < len(playlists) else ""))
    if playlists:
        print("    first by (name, id): %s (id %s, %d item(s))"
              % (playlists[0].name, playlists[0].id, playlists[0].items))
        print("    last  by (name, id): %s (id %s, %d item(s))"
              % (playlists[-1].name, playlists[-1].id, playlists[-1].items))
    playlistIds = [playlist.id for playlist in playlists]
    playlistsPresent = _presenceCheck("PlaylistEntity", "id", playlistIds)
    results.append(("getPlaylists returned rows", len(playlists) > 0))
    results.append(("playlists all present in PlaylistEntity", playlistsPresent))

    if not playlists:
        print("    skipped — no playlist to pick")
        results.append(("getPlaylist returned the requested playlist", False))
        results.append(("getPlaylist persisted with matching name", False))
        results.append(("playlist songs present in SongEntity", False))
        results.append(("position order preserved", False))
        results.append(("playlist join rows all resolve to SongEntity", False))
        fetchedSongIds = set()
    else:
        # Pick the playlist with the most items — never a fixed id.
        pickedPlaylist = max(playlists, key=lambda playlist: playlist.items)
        print("    picked playlist id %s (%s, %d item(s))"
              % (pickedPlaylist.id, pickedPlaylist.name, pickedPlaylist.items))

        # getPlaylist: single fetch, write-through, read-back by id.
        playlist = client.getPlaylist(pickedPlaylist.id)
        print("    getPlaylist: %s (owner %s, type %s, %d item(s))"
              % (playlist.name, playlist.owner, playlist.type, playlist.items))
        connection = sqlite3.connect(dbPath)
        try:
            playlistRow = connection.execute(
                "SELECT name FROM PlaylistEntity WHERE id = ?", (pickedPlaylist.id,)
            ).fetchone()
        finally:
            connection.close()
        print("    PlaylistEntity row for id %s: %s"
              % (pickedPlaylist.id, playlistRow[0] if playlistRow else "<missing>"))
        results.append(
            ("getPlaylist returned the requested playlist", playlist.id == pickedPlaylist.id)
        )
        results.append(
            ("getPlaylist persisted with matching name",
             playlistRow is not None and playlistRow[0] == playlist.name)
        )

        # getSongsFromPlaylist: no offset/limit -> auto-paginates the whole
        # playlist (bounded, unlike the song library). The read-back is
        # ordered by PlaylistSongEntity.position — the ordering contract.
        playlistSongs = client.getSongsFromPlaylist(pickedPlaylist.id)
        totalCount = (client.lastPayload or {}).get("total_count")
        print("    getSongsFromPlaylist(%s): %d returned, envelope total_count: %s"
              % (pickedPlaylist.id, len(playlistSongs), totalCount))
        if playlistSongs:
            print("    first by position: %s (id %s)"
                  % (playlistSongs[0].title, playlistSongs[0].id))
            print("    last  by position: %s (id %s)"
                  % (playlistSongs[-1].title, playlistSongs[-1].id))
        songIds = [song.id for song in playlistSongs]
        fetchedSongIds = set(songIds)
        results.append(
            ("playlist songs present in SongEntity",
             _presenceCheck("SongEntity", "mediaId", songIds))
        )

        # POSITION CONTRACT: each payload entry's playlisttrack is stored
        # verbatim as PlaylistSongEntity.position and the read-back orders by
        # it — so the join rows ordered by position must reproduce the
        # payload's (id, playlisttrack) sequence entry by entry.
        # Caveats: lastPayload holds the FINAL page — a playlist larger than
        # the page limit compares only that page (the count printout above
        # shows it). And upsert-only means a song REMOVED from the playlist
        # since a previous run keeps its stale join row and surfaces here as
        # a mismatch — re-run against a fresh DB to confirm a real diff.
        payloadSongs = (client.lastPayload or {}).get("song") or []
        expected = [(song.get("id"), song.get("playlisttrack")) for song in payloadSongs]
        connection = sqlite3.connect(dbPath)
        try:
            actual = [
                (row[0], row[1])
                for row in connection.execute(
                    "SELECT songId, position FROM PlaylistSongEntity "
                    "WHERE playlistId = ? ORDER BY position, songId",
                    (pickedPlaylist.id,),
                ).fetchall()
            ]
        finally:
            connection.close()
        firstMismatch = None
        for index in range(min(len(expected), len(actual))):
            if expected[index] != actual[index]:
                firstMismatch = index
                break
        if firstMismatch is None and len(expected) != len(actual):
            firstMismatch = min(len(expected), len(actual))
        if firstMismatch is None:
            print("    position order preserved: %d/%d" % (len(actual), len(expected)))
            results.append(("position order preserved", len(expected) > 0))
        else:
            exp = expected[firstMismatch] if firstMismatch < len(expected) else "<missing>"
            act = actual[firstMismatch] if firstMismatch < len(actual) else "<missing>"
            print("    FAIL position order at index %d: payload %s vs DB %s"
                  % (firstMismatch, exp, act))
            results.append(("position order preserved", False))

        # Every join row's songId must resolve to a SongEntity row — the
        # write-through upserts songs and join rows in ONE transaction, so a
        # dangling join row means the transaction contract broke.
        connection = sqlite3.connect(dbPath)
        try:
            dangling = connection.execute(
                "SELECT playlistSong.songId FROM PlaylistSongEntity playlistSong "
                "LEFT JOIN SongEntity song ON song.mediaId = playlistSong.songId "
                "WHERE playlistSong.playlistId = ? AND song.mediaId IS NULL",
                (pickedPlaylist.id,),
            ).fetchall()
        finally:
            connection.close()
        print("    join rows with no SongEntity row: %s"
              % (", ".join(row[0] for row in dangling) if dangling else "none"))
        results.append(("playlist join rows all resolve to SongEntity", not dangling))

    # History provenance (same as [4g]): playlist songs carry play data and
    # the write-through persists HistoryEntity rows for songs with non-null
    # last_played. Growth is legitimate — the check is provenance: every NEW
    # history row's mediaId must be a song fetched in this step.
    historyIdsAfter = _historyIds(dbPath)
    newHistoryIds = historyIdsAfter - historyIdsBefore
    connection = sqlite3.connect(dbPath)
    try:
        newHistoryMediaIds = {
            row[0]
            for row in connection.execute(
                "SELECT mediaId FROM HistoryEntity WHERE id IN (%s)"
                % ",".join("?" * len(newHistoryIds)),
                list(newHistoryIds),
            )
        } if newHistoryIds else set()
    finally:
        connection.close()
    unsourced = newHistoryMediaIds - fetchedSongIds
    print("    history rows before/after: %d / %d (%d new)"
          % (len(historyIdsBefore), len(historyIdsAfter), len(newHistoryIds)))
    print("    new history mediaIds not among fetched playlist songs: %s"
          % (", ".join(sorted(unsourced)) if unsourced else "none"))
    results.append(("playlist history writes all sourced from payload play data",
                    not unsourced))

    # --- Step 5: media URLs — getStreamUrl / getDownloadUrl + live fetch ---------
    # Placed BEFORE goodbye: the URLs embed the live session token, which step 6
    # destroys (unless --keep-session is passed). The library only BUILDS these
    # URLs (no network call, no DB write) — the GETs below are the script's own
    # verification, not library calls.
    print("\n[5] media URLs — getStreamUrl / getDownloadUrl + live fetch")
    # The song id is HARDCODED (MEDIA_SONG_ID), never picked from cached data:
    # 224408 is live-verified streaming via mpv on 2026-09-09, while ids
    # 180831 and 215751 have broken backing files server-side and HANG the
    # fetches. The DB is consulted only for the fallback's persisted songUrl —
    # the primary URLs need just the id and the live token.
    session = SessionRepository(Database(dbPath)).getSession()
    if session is None or not session.auth:
        print("    skipped — no live session")
        results.append(("stream URL constructed+fetchable", False))
        results.append(("download URL constructed+fetchable", False))
        results.append(("/play/ fallback fetchable with live token", False))
    else:
        mediaSongId = MEDIA_SONG_ID
        liveToken = session.auth
        connection = sqlite3.connect(dbPath)
        try:
            mediaRow = connection.execute(
                "SELECT title, songUrl FROM SongEntity WHERE mediaId = ?",
                (mediaSongId,),
            ).fetchone()
        finally:
            connection.close()
        mediaSongTitle = mediaRow[0] if mediaRow else None
        songUrl = mediaRow[1] if mediaRow else None
        print("    song id %s (%s) — hardcoded, live-verified via mpv 2026-09-09"
              % (mediaSongId, mediaSongTitle or "<not in DB>"))

        # PRIMARY: pure URL construction by the library (no network, no DB).
        streamUrl = client.getStreamUrl(mediaSongId, stats=0)
        downloadUrl = client.getDownloadUrl(mediaSongId, stats=0)
        streamConstructed = _checkMediaUrl(streamUrl, "stream", liveToken, mediaSongId)
        downloadConstructed = _checkMediaUrl(downloadUrl, "download", liveToken, mediaSongId)

        # Full URLs for immediate manual player testing — printed BEFORE the
        # fetches and flushed so they are on screen at once (the fetches can
        # be slow). The embedded token is this live session's: it dies with
        # goodbye in step 6 unless --keep-session was passed — either way the
        # URLs are for immediate manual use only.
        print("    MPV TEST STREAM URL: " + streamUrl, flush=True)
        print("    MPV TEST DOWNLOAD URL: " + downloadUrl, flush=True)

        streamOk, status, contentType, byteCount = _fetchRange(streamUrl)
        print("    GET stream URL (Range: bytes=0-1024): HTTP %s, Content-Type: %s, "
              "%d byte(s) read (cap %d)" % (status, contentType, byteCount, READ_CAP))
        results.append(("stream URL constructed+fetchable", streamConstructed and streamOk))

        downloadOk, status, contentType, byteCount = _fetchRange(downloadUrl)
        print("    GET download URL (Range: bytes=0-1024): HTTP %s, Content-Type: %s, "
              "%d byte(s) read (cap %d)" % (status, contentType, byteCount, READ_CAP))
        results.append(("download URL constructed+fetchable", downloadConstructed and downloadOk))

        # FALLBACK: the legacy /play/ web-player endpoint persisted as songUrl.
        # Keep scheme + host + path, rebuild the query with the LIVE token as
        # ssid (the stored query's own ssid/uid/bitrate/player params are
        # dropped). NOTE: stats suppression is unknown on this endpoint — this
        # test hit may record a play.
        if not songUrl:
            print("    /play/ fallback skipped — song %s has no persisted songUrl "
                  "(fetch it first, e.g. via getSong)" % mediaSongId)
            results.append(("/play/ fallback fetchable with live token", False))
        else:
            parts = urlsplit(songUrl)
            fallbackUrl = ("%s://%s%s?" % (parts.scheme, parts.netloc, parts.path)) + urlencode(
                {"ssid": liveToken, "type": "song", "oid": mediaSongId}
            )
            print("    fallback /play/ endpoint: %s://%s%s (query rebuilt: ssid=<live token>, "
                  "type=song, oid=%s)" % (parts.scheme, parts.netloc, parts.path, mediaSongId))
            print("    NOTE: stats suppression unknown on /play/ — this hit may record a play")
            fallbackOk, status, contentType, byteCount = _fetchRange(fallbackUrl)
            print("    GET /play/ fallback (Range: bytes=0-1024): HTTP %s, Content-Type: %s, "
                  "%d byte(s) read (cap %d)" % (status, contentType, byteCount, READ_CAP))
            results.append(("/play/ fallback fetchable with live token", fallbackOk))

    # --- Step 5b: flag/rate — interaction tier (mutating writes) ---------------
    # Placed BEFORE goodbye (step 6): both calls need the live session. The
    # song id is HARDCODED (MEDIA_SONG_ID) — the same live-verified id as the
    # media step. Test account: the writes are left in place, no state
    # restoration. flag()/rate() re-fetch the song through getSong and verify
    # the read-back themselves — a mismatch raises CacheVerificationError.
    print("\n[5b] flag/rate — interaction tier (song %s)" % MEDIA_SONG_ID)
    flagged = client.flag("song", MEDIA_SONG_ID, True)
    print("    flag read-back: %s" % flagged.flag)
    results.append(("flag applied+verified", flagged.flag is True))

    rated = client.rate("song", MEDIA_SONG_ID, 4)
    print("    rating read-back: %s" % rated.rating)
    results.append(("rating applied+verified", rated.rating == 4))

    # `rated` is the latest re-fetch: it should show BOTH writes — the flag
    # from the flag() call persisted through the rate() re-fetch.
    print("    fetched entity: flag=%s rating=%s" % (rated.flag, rated.rating))

    # --- Step 6: goodbye — session teardown --------------------------------------
    # Placed LAST: it destroys the session, so nothing after it may need auth.
    # --keep-session skips it entirely: the session (and the MPV TEST URLs
    # printed in step 5) stays alive for manual player testing.
    if keepSession:
        print("\n[6] goodbye — SKIPPED (--keep-session)")
        print("    session left alive for manual player testing — the MPV TEST URLs above")
        print("    keep working until the session expires server-side. Run without")
        print("    --keep-session to tear it down.")
    else:
        print("\n[6] goodbye — session teardown")
        goodbyeOk = False
        pingReportsUnauthenticated = False
        authenticatedCallRaises = False
        try:
            goodbyeResult = client.goodbye()
            goodbyeOk = goodbyeResult.success
            print("    goodbye: success=%s message=%s" % (goodbyeResult.success, goodbyeResult.message))
        except Exception as error:
            print("    goodbye raised: %s" % error)

        # ping after teardown: no session row remains, so ping takes its anonymous
        # path and reports authenticated=False (it does not raise).
        try:
            pingAfter = client.ping()
            pingReportsUnauthenticated = not pingAfter.authenticated
            print("    ping after goodbye: authenticated=%s" % pingAfter.authenticated)
        except Exception as error:
            print("    ping after goodbye raised unexpectedly: %s" % error)

        # An AUTHENTICATED call after goodbye must fail with the auth error — no
        # silent re-handshake on this client instance.
        try:
            client.getArtists(limit=1)
            print("    getArtists after goodbye returned — silent re-handshake happened!")
        except InvalidHandshakeError as error:
            authenticatedCallRaises = True
            print("    getArtists after goodbye raised InvalidHandshakeError: %s" % error)
        except Exception as error:
            print("    getArtists after goodbye raised the wrong error: %r" % error)

        sessionGone = SessionRepository(Database(dbPath)).getSession() is None
        print("    SessionEntity row after goodbye: %s" % ("<deleted>" if sessionGone else "STILL PRESENT"))
        if goodbyeOk and pingReportsUnauthenticated and authenticatedCallRaises and sessionGone:
            print("PASS goodbye destroyed session")
        else:
            print("FAIL goodbye destroyed session")
        results.append(("goodbye destroyed session",
                        goodbyeOk and pingReportsUnauthenticated and authenticatedCallRaises and sessionGone))

    # --- Step 7: verdict -----------------------------------------------------------
    print("\n[7] results")
    allOk = _report(results)
    print("\n" + ("PASS — all checks passed" if allOk else "FAIL — see above"))
    return 0 if allOk else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
