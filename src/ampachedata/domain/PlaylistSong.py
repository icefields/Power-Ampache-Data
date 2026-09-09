"""PlaylistSong domain entity — the playlist<->song join row. `position` is
the playlist ordering contract (the payload's playlisttrack, verbatim).
multiUserId stays in the DB layer."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PlaylistSong:
    id: str
    songId: str
    playlistId: str
    position: int
