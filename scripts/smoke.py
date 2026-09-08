#!/usr/bin/env python3
"""Manual smoke check against a REAL Ampache server. NOT a pytest file.

Usage:
    python scripts/smoke.py /path/to/scratch-musicdb.db

The DB must be a scratch COPY (it will be written to) whose CredentialsEntity
row already holds username + SHA256(password) key + serverUrl — e.g. seeded via
`python -m ampachedata init-credentials`. Credentials are read from that row
only: never from code, args, or env. The wrong-key check uses a second scratch
DB at <scratch>.wrongkey (created and deleted by this script).

Steps: (a) live handshake, (b) ping with the fresh token, (c) corrupt the
session row then ping — must silently re-auth, (d) wrong-key DB must raise a
typed AmpacheError. Exit 0 only if all pass."""
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ampachedata import AmpacheClient, AmpacheError
from ampachedata.data.auth.SessionManager import SessionManager
from ampachedata.data.db.Database import Database
from ampachedata.data.db.mappers.SessionMapper import mapSession
from ampachedata.data.db.repositories.CredentialsRepository import CredentialsRepository
from ampachedata.data.db.repositories.SessionRepository import SessionRepository

GARBAGE_TOKEN = "deadbeef" * 4
EXPIRED = "2000-01-01T00:00:00+00:00"


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: python scripts/smoke.py /path/to/scratch-musicdb.db", file=sys.stderr)
        return 2
    dbPath = argv[1]
    if not Path(dbPath).is_file():
        print("error: no such DB: " + dbPath, file=sys.stderr)
        return 2

    results = []
    oldToken = None
    newToken = None

    # (a) live handshake — real path: SessionManager.ensureSession persists the row.
    try:
        client = AmpacheClient(dbPath=dbPath)
        token = client._sessionManager.ensureSession()
        session = client._sessionRepository.getSession()
        oldToken = token
        print("a. handshake: OK  token=" + token[:4] + "...  expiry=" + session.sessionExpire)
        results.append(("a. live handshake", True))
    except Exception as exc:
        print("a. handshake: FAIL  " + type(exc).__name__ + ": " + str(exc))
        results.append(("a. live handshake", False))

    # (b) ping with the fresh token.
    if oldToken is not None:
        try:
            result = client.ping()
            print("b. ping: OK  authenticated=" + str(result.authenticated)
                  + "  api=" + result.api)
            results.append(("b. ping with fresh token", result.authenticated))
        except Exception as exc:
            print("b. ping: FAIL  " + type(exc).__name__ + ": " + str(exc))
            results.append(("b. ping with fresh token", False))
    else:
        print("b. ping: SKIP (no token from step a)")
        results.append(("b. ping with fresh token", False))

    # (c) corrupt the session row (garbage token, expired), ping must silently re-auth.
    if oldToken is not None:
        try:
            session = client._sessionRepository.getSession()
            row = mapSession({
                "auth": GARBAGE_TOKEN,
                "session_expire": EXPIRED,
                "api": session.api,
            })
            client._sessionRepository.upsertSession(row)
            result = client.ping()
            newToken = client._sessionRepository.getSession().auth
            differs = newToken != oldToken
            print("c. re-auth after corruption: OK  authenticated=" + str(result.authenticated)
                  + "  new token differs from old: " + str(differs))
            results.append(("c. silent re-auth on expired session", result.authenticated and differs))
        except Exception as exc:
            print("c. re-auth after corruption: FAIL  " + type(exc).__name__ + ": " + str(exc))
            results.append(("c. silent re-auth on expired session", False))
    else:
        print("c. re-auth after corruption: SKIP (no token from step a)")
        results.append(("c. silent re-auth on expired session", False))

    # (d) second scratch DB with a wrong key: expect a typed AmpacheError.
    wrongPath = dbPath + ".wrongkey"
    try:
        shutil.copyfile(dbPath, wrongPath)
        connection = sqlite3.connect(wrongPath)
        connection.execute("DELETE FROM SessionEntity")
        connection.execute(
            "UPDATE CredentialsEntity SET password = ?",
            ("0" * 64,),  # valid shape, wrong key — never printed
        )
        connection.commit()
        connection.close()
        wrongClient = AmpacheClient(dbPath=wrongPath)
        try:
            wrongClient.ping()
            print("d. wrong key: FAIL  ping unexpectedly succeeded")
            results.append(("d. wrong key raises typed AmpacheError", False))
        except AmpacheError as exc:
            print("d. wrong key: OK  raised " + type(exc).__name__)
            results.append(("d. wrong key raises typed AmpacheError", True))
        except Exception as exc:
            print("d. wrong key: FAIL  unexpected " + type(exc).__name__ + ": " + str(exc))
            results.append(("d. wrong key raises typed AmpacheError", False))
    except Exception as exc:
        print("d. wrong key: FAIL  setup error: " + type(exc).__name__ + ": " + str(exc))
        results.append(("d. wrong key raises typed AmpacheError", False))
    finally:
        Path(wrongPath).unlink(missing_ok=True)

    print("")
    allPassed = True
    for label, passed in results:
        print(("PASS  " if passed else "FAIL  ") + label)
        allPassed = allPassed and passed
    return 0 if allPassed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
