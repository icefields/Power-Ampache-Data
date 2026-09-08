"""artist JSON -> ArtistEntity row dict.

Dropped per Field Mapping (no ArtistEntity column — silent, by design):
prefix, basename, rating, averagerating, mbid, has_art (aliased away by art).
Nested albums/songs arrays (include=1 slots) are tolerated, never written here."""
import json


def mapArtist(artist: dict) -> dict:
    name = artist.get("name") or ""
    return {
        "id": artist.get("id") or "",
        "name": name,
        "albumCount": int(artist.get("albumcount") or 0),
        "songCount": int(artist.get("songcount") or 0),
        "genre": json.dumps(artist.get("genre") or [], separators=(",", ":")),
        "artUrl": artist.get("art") or "",
        "flag": 1 if artist.get("flag") else 0,
        "summary": artist.get("summary") or "",
        "time": int(artist.get("time") or 0),
        "yearFormed": int(artist.get("yearformed") or 0),
        "placeFormed": artist.get("placeformed") or "",
        "multiUserId": "",
        "searchName": _searchName(name),
    }


def _searchName(name: str) -> str:
    # Observed in real rows: "A Beautiful Lie (Instrumental)" -> "A Beautiful Lie Instrumental"
    return " ".join(name.replace("(", "").replace(")", "").split())
