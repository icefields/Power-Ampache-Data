"""album JSON -> AlbumEntity row.

Dropped per Field Mapping (no AlbumEntity column — silent, by design):
prefix, songartists, tracks, type, mbid, mbid_group, catalog, has_art
(aliased away by art -> artUrl).
Nested `artist` is a partial reference: extracted onto this row as
artistId/artistName; the artist row itself is skipped per the
partial-reference rule (INSERT OR REPLACE would blank its real columns).
`artists`/`genre` arrays are stored verbatim as JSON fragments in TEXT."""
import json


def mapAlbum(album: dict) -> dict:
    name = album.get("name") or ""
    artist = album.get("artist") or {}
    return {
        "id": album.get("id") or "",
        "name": name,
        "basename": album.get("basename") or "",
        "artistId": artist.get("id") or "",
        "artistName": artist.get("name") or "",
        "artists": json.dumps(album.get("artists") or [], separators=(",", ":")),
        "time": int(album.get("time") or 0),
        "year": int(album.get("year") or 0),
        "songCount": int(album.get("songcount") or 0),
        "diskCount": int(album.get("diskcount") or 0),
        "genre": json.dumps(album.get("genre") or [], separators=(",", ":")),
        "artUrl": album.get("art") or "",
        "flag": 1 if album.get("flag") else 0,
        "rating": int(album.get("rating") or 0),
        "averageRating": float(album.get("averagerating") or 0),
        "multiUserId": "",
        "searchName": _searchName(name),
    }


def _searchName(name: str) -> str:
    # Same normalization as ArtistMapper (observed in real rows).
    return " ".join(name.replace("(", "").replace(")", "").split())
