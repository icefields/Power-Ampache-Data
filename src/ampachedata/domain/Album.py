# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Album domain entity. Clean names — no JSON keys, no DB-only columns
(multiUserId, searchName stay in the DB layer)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Album:
    id: str
    name: str
    basename: str
    artistId: str
    artistName: str
    artists: str        # response's own JSON fragment, verbatim
    time: int
    year: int
    songCount: int
    diskCount: int
    genre: str          # response's own JSON fragment, verbatim
    artUrl: str
    rating: int
    averageRating: float
    flag: bool
