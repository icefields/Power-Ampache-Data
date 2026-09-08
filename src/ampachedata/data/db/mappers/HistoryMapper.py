"""song JSON -> HistoryEntity row (PK id mirrors the song id/mediaId so
repeated write-throughs refresh ONE row per song instead of duplicating).

lastPlayed is epoch MILLISECONDS (verified against existing rows); a null,
empty or unparseable last_played maps to 0. playCount mirrors the response
playcount (SongMapper also keeps it on SongEntity.playCount)."""
from datetime import datetime, timezone


def mapHistory(song: dict) -> dict:
    mediaId = song.get("id") or ""
    return {
        "id": mediaId,
        "mediaId": mediaId,
        "playCount": int(song.get("playcount") or 0),
        "lastPlayed": _epochMilliseconds(song.get("last_played")),
        "multiUserId": "",
    }


def _epochMilliseconds(isoTimestamp) -> int:
    if not isoTimestamp:
        return 0
    try:
        parsed = datetime.fromisoformat(str(isoTimestamp).replace("Z", "+00:00"))
    except ValueError:
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)
