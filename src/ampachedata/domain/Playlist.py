"""Playlist domain entity. Clean names — no JSON keys, no DB-only columns
(flag, multiUserId stay in the DB layer)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Playlist:
    id: str
    name: str
    owner: str
    items: int
    type: str
    artUrl: str
    preciseRating: float
    rating: int
    averageRating: float
