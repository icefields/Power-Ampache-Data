# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Packaged schema: path constant and the opt-in database creation helper.

The library never creates or alters schema on its own — createDatabase is
called explicitly by the caller, once, on a path that does not exist yet.
Python 3.8 compatible: no importlib.resources, open() relative to __file__."""
import os
import sqlite3

from .errors import DatabaseError

# schema.sql ships in the package root (src/ampachedata/), one level up from
# this module — hence the ".." in the join.
SCHEMA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "schema.sql")
)


def createDatabase(dbPath: str) -> None:
    """Create a new SQLite database at dbPath from the bundled schema.

    Opt-in helper. Raises DatabaseError when dbPath already exists — the
    helper never alters an existing database.
    """
    if os.path.exists(dbPath):
        raise DatabaseError(
            "database already exists at " + dbPath +
            " — createDatabase never alters an existing database"
        )
    try:
        connection = sqlite3.connect(dbPath)
        try:
            with open(SCHEMA_PATH, encoding="utf-8") as schemaFile:
                connection.executescript(schemaFile.read())
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise DatabaseError(
            "could not create database at " + dbPath + " — " + str(error)
        )
