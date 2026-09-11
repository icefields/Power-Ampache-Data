# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Bootstrap tests: temp DB per test (schema from the packaged schema.sql), no network."""
import hashlib
import sqlite3
from pathlib import Path

import pytest

from ampachedata import (
    CredentialValidationError,
    DatabaseError,
    storeCredentialsFromKey,
    storeCredentialsFromPassword,
)

SERVER = "https://demo.ampache.dev"
CLEARTEXT = "correct horse battery staple"
EXPECTED_HASH = hashlib.sha256(CLEARTEXT.encode("utf-8")).hexdigest()
VALID_KEY = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"  # sha256("test")


def readCredentials(dbPath):
    connection = sqlite3.connect(dbPath)
    row = connection.execute(
        "SELECT username, password, authToken, serverUrl, multiUserId FROM CredentialsEntity"
    ).fetchone()
    connection.close()
    return row


def rowCount(dbPath, table):
    connection = sqlite3.connect(dbPath)
    count = connection.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0]
    connection.close()
    return count


def tableCounts(dbPath):
    connection = sqlite3.connect(dbPath)
    names = [r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")]
    counts = {name: connection.execute(
        'SELECT COUNT(*) FROM "' + name + '"').fetchone()[0] for name in names}
    connection.close()
    return counts


def testPasswordPathStoresOnlyTheDigest(dbPath):
    storeCredentialsFromPassword(dbPath, "user", SERVER, CLEARTEXT)
    assert readCredentials(dbPath) == ("user", EXPECTED_HASH, "", SERVER, "")


def testCleartextNeverTouchesDisk(dbPath):
    storeCredentialsFromPassword(dbPath, "user", SERVER, CLEARTEXT)
    raw = Path(dbPath).read_bytes()
    assert CLEARTEXT.encode("utf-8") not in raw
    assert EXPECTED_HASH.encode("utf-8") in raw


def testWritesExactlyOneRowAndTouchesNoOtherTable(dbPath):
    storeCredentialsFromPassword(dbPath, "user", SERVER, CLEARTEXT)
    counts = tableCounts(dbPath)
    assert counts.pop("CredentialsEntity") == 1
    assert set(counts.values()) == {0}  # SessionEntity and every other table empty


def testRerunOverwritesTheSingleRow(dbPath):
    storeCredentialsFromPassword(dbPath, "user", SERVER, CLEARTEXT)
    storeCredentialsFromKey(dbPath, "other", "https://other.example", VALID_KEY)
    assert rowCount(dbPath, "CredentialsEntity") == 1
    assert readCredentials(dbPath) == ("other", VALID_KEY, "", "https://other.example", "")


def testKeyPathStoresValidKeyVerbatim(dbPath):
    storeCredentialsFromKey(dbPath, "user", SERVER, VALID_KEY)
    assert readCredentials(dbPath)[1] == VALID_KEY


@pytest.mark.parametrize("badKey", [
    "",
    "a" * 63,            # too short
    "a" * 65,            # too long
    "A" * 64,            # uppercase hex rejected
    "g" * 64,            # non-hex
    VALID_KEY[:-1] + "Z",
])
def testKeyPathRejectsInvalidKeys(dbPath, badKey):
    with pytest.raises(CredentialValidationError):
        storeCredentialsFromKey(dbPath, "user", SERVER, badKey)
    assert rowCount(dbPath, "CredentialsEntity") == 0


def testValidationErrorNeverContainsTheSecret(dbPath):
    canary = "s3cret-canary-value"
    with pytest.raises(CredentialValidationError) as excInfo:
        storeCredentialsFromKey(dbPath, "user", SERVER, canary)
    assert canary not in str(excInfo.value)


@pytest.mark.parametrize("username,serverUrl", [
    ("", SERVER),
    ("   ", SERVER),
    ("user", ""),
    ("user", "demo.ampache.dev"),  # missing scheme
])
def testRejectsBadUsernameAndServerUrl(dbPath, username, serverUrl):
    with pytest.raises(CredentialValidationError):
        storeCredentialsFromPassword(dbPath, username, serverUrl, CLEARTEXT)
    assert rowCount(dbPath, "CredentialsEntity") == 0


def testEmptyPasswordRejected(dbPath):
    with pytest.raises(CredentialValidationError):
        storeCredentialsFromPassword(dbPath, "user", SERVER, "")


def testMissingDatabaseRaises(dbPath):
    missing = str(Path(dbPath).with_name("absent.db"))
    with pytest.raises(DatabaseError):
        storeCredentialsFromPassword(missing, "user", SERVER, CLEARTEXT)
