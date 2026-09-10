# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""CLI tests for python -m ampachedata init-credentials."""
import getpass
import hashlib
import io
import sqlite3
import sys

import pytest

from ampachedata.__main__ import main

SERVER = "https://demo.ampache.dev"
CLEARTEXT = "correct horse battery staple"
EXPECTED_HASH = hashlib.sha256(CLEARTEXT.encode("utf-8")).hexdigest()
VALID_KEY = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"  # sha256("test")


class FakeTty(io.StringIO):
    def isatty(self):
        return True


def readPasswordColumn(dbPath):
    connection = sqlite3.connect(dbPath)
    rows = connection.execute("SELECT password FROM CredentialsEntity").fetchall()
    connection.close()
    return rows


def baseArgs(dbPath):
    return ["init-credentials", "--db-path", dbPath,
            "--username", "user", "--server-url", SERVER]


def testPasswordStdin(dbPath, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(CLEARTEXT + "\n"))
    assert main(baseArgs(dbPath) + ["--password-stdin"]) == 0
    assert readPasswordColumn(dbPath) == [(EXPECTED_HASH,)]


def testPasswordStdinStripsOnlyTheNewline(dbPath, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(CLEARTEXT + "\r\n"))
    assert main(baseArgs(dbPath) + ["--password-stdin"]) == 0
    assert readPasswordColumn(dbPath) == [(EXPECTED_HASH,)]


def testPasswordEnv(dbPath, monkeypatch):
    monkeypatch.setenv("AMPACHE_TEST_PASSWORD", CLEARTEXT)
    assert main(baseArgs(dbPath) + ["--password-env", "AMPACHE_TEST_PASSWORD"]) == 0
    assert readPasswordColumn(dbPath) == [(EXPECTED_HASH,)]


def testPasswordEnvMissingVar(dbPath, monkeypatch):
    monkeypatch.delenv("AMPACHE_TEST_MISSING", raising=False)
    assert main(baseArgs(dbPath) + ["--password-env", "AMPACHE_TEST_MISSING"]) == 2
    assert readPasswordColumn(dbPath) == []


def testKeyFlag(dbPath):
    assert main(baseArgs(dbPath) + ["--key", VALID_KEY]) == 0
    assert readPasswordColumn(dbPath) == [(VALID_KEY,)]


def testKeyStdin(dbPath, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(VALID_KEY + "\n"))
    assert main(baseArgs(dbPath) + ["--key-stdin"]) == 0
    assert readPasswordColumn(dbPath) == [(VALID_KEY,)]


def testInvalidKeyExits2AndLeaksNothing(dbPath, capsys):
    assert main(baseArgs(dbPath) + ["--key", "not-hex"]) == 2
    assert readPasswordColumn(dbPath) == []
    assert "not-hex" not in capsys.readouterr().err


def testInteractiveGetpass(dbPath, monkeypatch):
    monkeypatch.setattr(sys, "stdin", FakeTty())
    answers = iter([CLEARTEXT, CLEARTEXT])
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(answers))
    assert main(baseArgs(dbPath)) == 0
    assert readPasswordColumn(dbPath) == [(EXPECTED_HASH,)]


def testInteractiveConfirmationMismatch(dbPath, monkeypatch):
    monkeypatch.setattr(sys, "stdin", FakeTty())
    answers = iter([CLEARTEXT, "different"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(answers))
    assert main(baseArgs(dbPath)) == 2
    assert readPasswordColumn(dbPath) == []


def testNonTtyWithoutSourceFails(dbPath, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(CLEARTEXT + "\n"))  # not a TTY
    assert main(baseArgs(dbPath)) == 2
    assert readPasswordColumn(dbPath) == []


def testNonInteractiveRequiresUsernameAndServerUrl(dbPath, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(CLEARTEXT + "\n"))
    assert main(["init-credentials", "--db-path", dbPath, "--password-stdin"]) == 2
    assert readPasswordColumn(dbPath) == []


def testSecretSourcesAreMutuallyExclusive(dbPath):
    with pytest.raises(SystemExit):
        main(baseArgs(dbPath) + ["--password-stdin", "--key", VALID_KEY])


def testMissingDatabaseExits1(tmp_path):
    args = ["init-credentials", "--db-path", str(tmp_path / "absent.db"),
            "--username", "user", "--server-url", SERVER, "--key", VALID_KEY]
    assert main(args) == 1


def testOutputNeverContainsSecretMaterial(dbPath, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(CLEARTEXT + "\n"))
    assert main(baseArgs(dbPath) + ["--password-stdin"]) == 0
    captured = capsys.readouterr()
    assert CLEARTEXT not in captured.out and CLEARTEXT not in captured.err
    assert EXPECTED_HASH not in captured.out and EXPECTED_HASH not in captured.err
