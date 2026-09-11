# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Schema helper tests: opt-in createDatabase against tmp paths, no network."""
import os
import sqlite3

import pytest

from ampachedata import DatabaseError, createDatabase
from ampachedata.data.Schema import SCHEMA_PATH

EXPECTED_TABLE_COUNT = 18


def tableNames(dbPath):
    connection = sqlite3.connect(dbPath)
    names = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    connection.close()
    return names


def testCreateDatabaseCreatesFileWithAllTables(tmp_path):
    target = str(tmp_path / "musicdb.db")
    createDatabase(target)
    assert os.path.isfile(target)
    names = tableNames(target)
    assert len(names) == EXPECTED_TABLE_COUNT
    assert {"SongEntity", "CredentialsEntity", "SessionEntity"} <= names


def testCreateDatabaseRefusesExistingFileLeavesItUntouched(tmp_path):
    target = tmp_path / "musicdb.db"
    target.write_bytes(b"sentinel")
    with pytest.raises(DatabaseError):
        createDatabase(str(target))
    assert target.read_bytes() == b"sentinel"


def testSchemaPathResolvesToExistingFile():
    assert os.path.isfile(SCHEMA_PATH)
