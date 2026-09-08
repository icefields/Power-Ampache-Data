"""song JSON -> HistoryEntity row, or None when the song was never played.

PK id mirrors the song id/mediaId so repeated write-throughs refresh ONE row
per song instead of duplicating.

lastPlayed is epoch MILLISECONDS (verified against existing rows). A falsy
(null/empty) or unparseable last_played means "never played": mapHistory
returns None and the caller writes NO row — epoch-0 rows are never emitted.
playCount mirrors the response playcount (SongMapper also keeps it on
SongEntity.playCount)."""
from datetime import datetime, timezone
from typing import Optional


def mapHistory(song: dict) -> Optional[dict]:
    lastPlayed = _epochMilliseconds(song.get("last_played"))
    if lastPlayed is None:
        return None
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
