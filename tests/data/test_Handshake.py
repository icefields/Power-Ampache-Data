# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Auth composition against the known-good vector (CONVENTIONS: auth test)."""
from ampachedata.data.auth.Handshake import buildPassphrase, sha256Hex

KEY = "2a97516c354b68848cdbd8f54a226a0a55b21ed138e207ad6c5cbb9c00aa5aea"
EXPECTED_PASSPHRASE = "53ec985108e46054a949f8d5c609797690711ba0571bdef28b8226e1aa845034"


def testKeyIsSha256OfPassword():
    assert sha256Hex("demo") == KEY


def testPassphraseComposition():
    assert buildPassphrase("1700000000", KEY) == EXPECTED_PASSPHRASE
