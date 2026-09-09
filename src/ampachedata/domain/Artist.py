"""Artist domain entity. Clean names — no JSON keys, no DB-only columns
(searchName, multiUserId stay in the DB layer)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Artist:
    id: str
    name: str
    albumCount: int
    songCount: int
    genre: str        # response's own JSON fragment, verbatim
    artUrl: str
    summary: str
    time: int
    yearFormed: int
    placeFormed: str
    flag: bool
