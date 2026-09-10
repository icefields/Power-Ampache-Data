# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""SQL-only access to HistoryEntity (PK id — mirrors the song id/mediaId, see
HistoryMapper). Never sees HTTP.

Transaction semantics: upserts commit only when this call owns the transaction
(none open on the connection). Inside a caller-owned transaction (AmpacheClient
opens one with BEGIN for multi-repository write-throughs) the commit stays with
the caller so all rows commit as ONE unit."""
from ....domain.History import History

_COLUMNS = ("id", "mediaId", "playCount", "lastPlayed", "multiUserId")

_UPSERT_SQL = "INSERT OR REPLACE INTO HistoryEntity ({}) VALUES ({})".format(
    ", ".join(_COLUMNS),
    ", ".join("?" * len(_COLUMNS)),
)

_SELECT_SQL = "SELECT mediaId, playCount, lastPlayed FROM HistoryEntity"


def _toHistory(row) -> History:
    return History(
        mediaId=row["mediaId"],
        playCount=row["playCount"],
        lastPlayed=row["lastPlayed"],
    )


class HistoryRepository:
    def __init__(self, database):
        self._database = database

    def upsertHistories(self, rows) -> None:
        # Commits only when this call owns the transaction (none open yet).
        # Inside a caller-owned transaction the commit stays with the caller so
        # multi-repository write-throughs commit (or roll back) as ONE unit.
        values = [[row[column] for column in _COLUMNS] for row in rows]
        connection = self._database.connection
        ownsTransaction = not connection.in_transaction
        connection.executemany(_UPSERT_SQL, values)
        if ownsTransaction:
            connection.commit()

    def getHistories(self):
        """Play-history ordering is DB-derived: lastPlayed DESC (most recent
        first), then mediaId for a stable order among ties."""
        rows = self._database.connection.execute(
            _SELECT_SQL + " ORDER BY lastPlayed DESC, mediaId"
        ).fetchall()
        return [_toHistory(row) for row in rows]
