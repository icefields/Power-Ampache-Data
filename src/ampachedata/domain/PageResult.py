# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Paged read result for the query tier: one page of rows plus the total row
count. A result type, not an entity — no table maps to it."""
from dataclasses import dataclass
from typing import Generic, List, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PageResult(Generic[T]):
    """One page of a DB-only read.

    `total` is the SQL COUNT over the full filtered set — not this page's
    length, and never the server's total_count (it lies) — so callers can
    compute page counts and know when to stop paging."""

    rows: List[T]
    total: int
