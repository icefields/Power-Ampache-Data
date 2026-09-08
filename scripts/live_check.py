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

from ampachedata import AmpacheClient

USAGE = "usage: python scripts/live_check.py <path-to-musicdb.db>"
ARTIST_LIMIT = 50
_TABLES = ("ArtistEntity", "AlbumEntity", "SongEntity")


def _counts(dbPath):
    connection = sqlite3.connect(dbPath)
    try:
        return {
            table: connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            for table in _TABLES
        }
    finally:
        connection.close()


def _report(results):
    allOk = True
    for label, ok in results:
        allOk = allOk and ok
        print(("PASS" if ok else "FAIL") + " " + label)
    return allOk


def main(argv):
    if len(argv) != 2:
        print(USAGE)
        return 2
    dbPath = argv[1]
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

    # --- Step 5: verdict -----------------------------------------------------------
    print("\n[5] results")
    allOk = _report(results)
    print("\n" + ("PASS — all checks passed" if allOk else "FAIL — see above"))
    return 0 if allOk else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
