"""Live smoke check against a real Ampache server — NOT a unit test.

pytest never collects this file (pyproject testpaths = tests/); run it by
hand against a musicdb.db that already holds credentials. Everything the
client needs (username, password hash, serverUrl) comes from the DB — the
script takes only the DB path, never a secret:

    python scripts/live_check.py /path/to/musicdb.db

Requires the package installed (pip install -e .); no sys.path hacks."""
import sys

from ampachedata import AmpacheClient

USAGE = "usage: python scripts/live_check.py <path-to-musicdb.db>"


def main(argv):
    if len(argv) != 2:
        print(USAGE)
        return 2
    client = AmpacheClient(dbPath=argv[1])
    ping = client.ping()
    print("ping: authenticated=" + str(ping.authenticated) + " api=" + str(ping.api))
    artists = client.getArtists()
    print("artists read back from DB: " + str(len(artists)))
    for artist in artists[:5]:
        print("  - " + artist.name)
    print("total_count from last payload: " + str(client.lastPayload.get("total_count")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
