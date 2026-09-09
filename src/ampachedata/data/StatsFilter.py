"""stats method filter values — no magic strings outside this enum.

All seven documented values live here; AmpacheClient's song family currently
exposes recent, frequent, forgotten and random (each method's docstring says
which DB-derived read-back order it uses)."""
from enum import Enum


class StatsFilter(str, Enum):
    NEWEST = "newest"
    HIGHEST = "highest"
    FREQUENT = "frequent"
    RECENT = "recent"
    FORGOTTEN = "forgotten"
    FLAGGED = "flagged"
    RANDOM = "random"
