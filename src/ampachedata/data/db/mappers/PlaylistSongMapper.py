"""playlist_songs song entry -> PlaylistSongEntity join row.

`position` is the ordering contract: the entry's `playlisttrack` value,
copied verbatim — never renumbered, never sorted by the mapper. The payload
carries no row id for the join, so `id` is synthesized as
"{playlistId}:{songId}": re-fetching a playlist refreshes positions via
INSERT OR REPLACE instead of duplicating rows. Known limitation: the same
song twice in one playlist collapses into a single row (last write wins) —
the schema's PK gives no way to represent duplicates."""


def mapPlaylistSong(song: dict, playlistId: str) -> dict:
    songId = song.get("id") or ""
    return {
        "id": playlistId + ":" + songId,
        "songId": songId,
        "playlistId": playlistId,
        "position": int(song.get("playlisttrack") or 0),
        "multiUserId": "",
    }
