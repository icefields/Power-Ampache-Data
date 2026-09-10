# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
from datetime import datetime, timezone

from ampachedata.data.db.mappers.HistoryMapper import mapHistory

FALLBACK = 1_700_000_000_000


def testNullLastPlayedWithPlaycountAndFallbackUsesFallback():
    row = mapHistory(
        {"id": "253893", "playcount": 1, "last_played": None},
        fallbackLastPlayed=FALLBACK,
    )
    assert row == {
        "id": "253893",
        "mediaId": "253893",
        "playCount": 1,
        "lastPlayed": FALLBACK,
        "multiUserId": "",
    }


def testNullLastPlayedWithFallbackButZeroPlaycountReturnsNone():
    assert mapHistory(
        {"id": "253893", "playcount": 0, "last_played": None},
        fallbackLastPlayed=FALLBACK,
    ) is None


def testRealLastPlayedWinsOverFallback():
    row = mapHistory(
        {"id": "1", "playcount": 4, "last_played": "2024-01-15T10:30:00+00:00"},
        fallbackLastPlayed=FALLBACK,
    )
    expected = int(datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc).timestamp() * 1000)
    assert row is not None
    assert row["lastPlayed"] == expected


def testUnparseableLastPlayedWithPlaycountAndFallbackUsesFallback():
    row = mapHistory(
        {"id": "2", "playcount": 2, "last_played": "not-a-date"},
        fallbackLastPlayed=FALLBACK,
    )
    assert row is not None
    assert row["lastPlayed"] == FALLBACK


def testNullLastPlayedWithoutFallbackReturnsNone():
    assert mapHistory({"id": "1", "playcount": 3, "last_played": None}) is None
    assert mapHistory({"id": "1", "playcount": 3}) is None
