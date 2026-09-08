"""Live smoke check against a real Ampache server — NOT a unit test.

pytest never collects this file (pyproject testpaths = tests/); run it by
hand against a musicdb.db that already holds credentials. Everything the
client needs (username, password hash, serverUrl) comes from the DB — the
script takes only the DB path, never a secret:

    python scripts/live_check.py /path/to/musicdb.db

Requires the package installed (pip install -e .); no sys.path hacks."""
import sqlite3
import sys

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

    # --- Step 1: ping + getArtists ------------------------------------------------
    print("\n[1] ping + getArtists(limit=%d)" % ARTIST_LIMIT)
    ping = client.ping()
    print("    ping: authenticated=" + str(ping.authenticated) + " api=" + str(ping.api))
    artists = client.getArtists(limit=ARTIST_LIMIT)
    totalCount = (client.lastPayload or {}).get("total_count")
    print("    returned: %d artist(s), envelope total_count: %s" % (len(artists), totalCount))
    if artists:
        print("    first by searchName: %s (id %s)" % (artists[0].name, artists[0].id))
        print("    last  by searchName: %s (id %s)" % (artists[-1].name, artists[-1].id))
    results.append(("ping authenticated", ping.authenticated))
    results.append(("getArtists returned rows", len(artists) > 0))

    # --- Step 2: getArtist with include -------------------------------------------
    print("\n[2] getArtist(id, include=albums,songs)")
    if not artists:
        print("    skipped — no artist to pick")
        results.append(("getArtist include", False))
        artist = None
        albumsAdded = songsAdded = 0
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
    print("    ArtistEntity: %+d row(s)" % (after["ArtistEntity"] - before["ArtistEntity"]))
    results.append(("artist rows written", after["ArtistEntity"] > before["ArtistEntity"]))
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

    # --- Step 4: verdict -----------------------------------------------------------
    print("\n[4] results")
    allOk = _report(results)
    print("\n" + ("PASS — all checks passed" if allOk else "FAIL — see above"))
    return 0 if allOk else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
