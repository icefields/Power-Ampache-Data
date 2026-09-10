# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Playlist domain entity. Clean names — no JSON keys, no DB-only columns
(multiUserId stay in the DB layer)."""
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
    flag: bool
