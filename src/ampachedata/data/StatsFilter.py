"""stats method filter values — no magic strings outside this enum.

All seven documented values live here; AmpacheClient's song and album
families currently expose newest, highest, recent, frequent, forgotten and
random (flagged is not exposed yet). Each method's docstring says which
DB-derived read-back order it uses, or documents the LIMITATION when the
stats ordering can't be derived from stored columns."""
from enum import Enum


class StatsFilter(str, Enum):
    NEWEST = "newest"
    HIGHEST = "highest"
    FREQUENT = "frequent"
    RECENT = "recent"
    FORGOTTEN = "forgotten"
    FLAGGED = "flagged"
    RANDOM = "random"
