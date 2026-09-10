# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Opens the caller-provided musicdb.db. The library NEVER creates or alters schema."""
import os
import sqlite3

from ..errors import DatabaseError


class Database:
    def __init__(self, dbPath: str):
        if not os.path.exists(dbPath):
            raise DatabaseError(
                "musicdb.db not found at " + dbPath +
                " — the library never creates schema; provide an existing database"
            )
        self._connection = sqlite3.connect(dbPath)
        self._connection.row_factory = sqlite3.Row

    @property
    def connection(self):
        return self._connection

    def close(self):
        self._connection.close()
