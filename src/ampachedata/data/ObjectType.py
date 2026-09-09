"""Object types accepted by the interaction tier (flag/rate) — no magic strings.

Only the four types this library models as domain entities; the spec's
podcast/video/tvshow types have no entity (and no getter) here."""
from enum import Enum


class ObjectType(str, Enum):
    SONG = "song"
    ALBUM = "album"
    ARTIST = "artist"
    PLAYLIST = "playlist"
