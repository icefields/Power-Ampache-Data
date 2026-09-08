"""History domain entity — play history for one song, keyed by mediaId (the
HistoryEntity row id mirrors it; see HistoryMapper). Clean names — no JSON
keys, no DB-only columns (multiUserId stays in the DB layer)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class History:
    mediaId: str
    playCount: int
    lastPlayed: int  # epoch milliseconds
