# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""LIKE pattern building for the query tier's search methods.

User input matches LITERALLY: backslash, % and _ are escaped, and every
search pairs the pattern with LIKE ? ESCAPE '\\' — a user can never inject
wildcards (the server may treat ? as a wildcard; our own search must not
treat % and _ as user-controlled ones).

SQLite LIKE is case-insensitive for ASCII only: non-ASCII names (e.g.
Cyrillic) match case-sensitively. No normalization machinery — this is
documented behavior, not a bug."""


def likePattern(query: str) -> str:
    """Return query wrapped in %...% with \\, %, _ escaped, for use with
    `LIKE ? ESCAPE '\\'`. Backslash is escaped FIRST. Callers must reject
    empty queries before calling — an empty query would build '%%'
    (match-everything)."""
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "%" + escaped + "%"
