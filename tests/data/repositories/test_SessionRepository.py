# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Write-through storage: upsert -> read back; single-row invariant."""
import sqlite3

from ampachedata.data.db.Database import Database
from ampachedata.data.db.mappers.SessionMapper import mapSession
from ampachedata.data.db.repositories.SessionRepository import SessionRepository


def testUpsertThenReadBack(dbPath, handshakePayload):
    repository = SessionRepository(Database(dbPath))
    repository.upsertSession(mapSession(handshakePayload))
    session = repository.getSession()
    assert session.auth == "0c45633f51b0e264a2260ebfa406e1ad"
    assert session.sessionExpire == "2022-08-17T06:21:00+00:00"
    assert session.api == "8.0.0"
    assert session.counts["songs"] == 75
    assert session.counts["playlistsSearches"] == 22


def testUpsertKeepsSingleRow(dbPath, handshakePayload):
    repository = SessionRepository(Database(dbPath))
    repository.upsertSession(mapSession(handshakePayload))
    row = mapSession(handshakePayload)
    row["auth"] = "f" * 32
    repository.upsertSession(row)
    count = sqlite3.connect(dbPath).execute("SELECT COUNT(*) FROM SessionEntity").fetchone()[0]
    assert count == 1
    assert repository.getSession().auth == "f" * 32
