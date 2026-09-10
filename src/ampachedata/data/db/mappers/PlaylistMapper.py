# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""playlist JSON -> PlaylistEntity row.

Dropped per Field Mapping (no PlaylistEntity column — silent, by design):
has_access, has_collaborate, md5, last_update, time; has_art is aliased
away by art -> artUrl. playlist_folder_id / playlist_folder_sort_order
(newer spec fields, not in the examples) have no column either — added to
the drop list per CONVENTIONS. The `user` summary object ({id, username})
is a partial reference: never upserted into UserEntity (INSERT OR REPLACE
would blank its real columns) — `owner` (a plain string in the response)
carries the username onto this row. `items` arrives as an integer in the
examples; the spec also allows an array — its length is stored then."""


def mapPlaylist(playlist: dict) -> dict:
    items = playlist.get("items")
    if isinstance(items, list):
        items = len(items)
    return {
        "id": playlist.get("id") or "",
        "name": playlist.get("name") or "",
        "owner": playlist.get("owner") or "",
        "items": int(items or 0),
        "type": playlist.get("type") or "",
        "artUrl": playlist.get("art") or "",
        "flag": 1 if playlist.get("flag") else 0,
        "preciseRating": float(playlist.get("preciserating") or 0),
        "rating": int(playlist.get("rating") or 0),
        "averageRating": float(playlist.get("averagerating") or 0),
        "multiUserId": "",
    }
