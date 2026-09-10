# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""song JSON -> HistoryEntity row, or None when the song was never played.

PK id mirrors the song id/mediaId so repeated write-throughs refresh ONE row
per song instead of duplicating.

lastPlayed is epoch MILLISECONDS (verified against existing rows). A falsy
(null/empty) or unparseable last_played means "never played": mapHistory
returns None and the caller writes NO row — epoch-0 rows are never emitted.
playCount mirrors the response playcount (SongMapper also keeps it on
SongEntity.playCount).

fallbackLastPlayed (API6 null-last_played workaround): API 6.x servers
(verified live on Ampache 7.9.2 / API 6.9.1) return played songs
(playcount > 0) with last_played: null. When the caller passes
fallbackLastPlayed (epoch ms) for such a song, the fallback becomes
lastPlayed instead of returning None. Callers fabricate it as
now_ms - response_index because the stats-recent response order IS the
recency order (PowerAmpache 2 precedent — index subtraction preserves
it). With fallbackLastPlayed=None the behavior is IDENTICAL to before:
null/unparseable last_played -> None, no row, no exceptions."""
from datetime import datetime, timezone
from typing import Optional


def mapHistory(song: dict, fallbackLastPlayed: Optional[int] = None) -> Optional[dict]:
    lastPlayed = _epochMilliseconds(song.get("last_played"))
    if lastPlayed is None:
        if fallbackLastPlayed is None:
            # Historic behavior, unchanged: null/unparseable last_played with
            # no caller fallback means "never played" — no row, no exceptions.
            return None
        # API6 workaround (see module docstring): the server listed this song
        # as played (playcount > 0) but omitted last_played — use the
        # caller-fabricated fallback so the recency order survives.
        if int(song.get("playcount") or 0) <= 0:
            return None
        lastPlayed = fallbackLastPlayed
    mediaId = song.get("id") or ""
    return {
        "id": mediaId,
        "mediaId": mediaId,
        "playCount": int(song.get("playcount") or 0),
        "lastPlayed": lastPlayed,
        "multiUserId": "",
    }


def _epochMilliseconds(isoTimestamp) -> Optional[int]:
    if not isoTimestamp:
        return None
    try:
        parsed = datetime.fromisoformat(str(isoTimestamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)
