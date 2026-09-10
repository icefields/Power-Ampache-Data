# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""song JSON -> SongEntity row (id -> mediaId, url -> songUrl).

Dropped per Field Mapping (no SongEntity column — silent, by design):
license, replaygain_album_gain, replaygain_album_peak, r128_album_gain,
r128_track_gain (track replaygain IS stored).
`last_played`/`playcount` also belong on HistoryEntity (lastPlayed as epoch
ms) — HistoryMapper builds that row and AmpacheClient upserts it alongside
this one in the same transaction; playcount still fills SongEntity.playCount.
Nested artist/album/albumartist are partial references: extracted onto this
row (ids, names, mbids); the referenced rows themselves are skipped per the
partial-reference rule. `genre`/`artists` arrays are stored verbatim as JSON
fragments in TEXT columns."""
import json


def mapSong(song: dict) -> dict:
    title = song.get("title") or ""
    album = song.get("album") or {}
    artist = song.get("artist") or {}
    albumArtist = song.get("albumartist") or {}
    return {
        "mediaId": song.get("id") or "",
        "title": title,
        "albumId": album.get("id") or "",
        "albumName": album.get("name") or "",
        "artistId": artist.get("id") or "",
        "artistName": artist.get("name") or "",
        "albumArtist": albumArtist.get("name") or "",
        "songUrl": song.get("url") or "",
        "imageUrl": song.get("art") or "",
        "bitrate": int(song.get("bitrate") or 0),
        "streamBitrate": int(song.get("stream_bitrate") or 0),
        "catalog": int(song.get("catalog") or 0),
        "channels": int(song.get("channels") or 0),
        "composer": song.get("composer") or "",
        "filename": song.get("filename") or "",
        "genre": json.dumps(song.get("genre") or [], separators=(",", ":")),
        "mime": song.get("mime"),
        "playCount": int(song.get("playcount") or 0),
        "playlistTrackNumber": int(song.get("playlisttrack") or 0),
        "rateHz": int(song.get("rate") or 0),
        "size": int(song.get("size") or 0),
        "time": int(song.get("time") or 0),
        "trackNumber": int(song.get("track") or 0),
        "year": int(song.get("year") or 0),
        "name": song.get("name") or "",
        "mode": song.get("mode"),
        "artists": json.dumps(song.get("artists") or [], separators=(",", ":")),
        "flag": 1 if song.get("flag") else 0,
        "streamFormat": song.get("stream_format"),
        "format": song.get("format"),
        "streamMime": song.get("stream_mime"),
        "publisher": song.get("publisher"),
        "replayGainTrackGain": song.get("replaygain_track_gain"),
        "replayGainTrackPeak": song.get("replaygain_track_peak"),
        "disk": int(song.get("disk") or 0),
        "diskSubtitle": song.get("disksubtitle") or "",
        "mbId": song.get("mbid") or "",
        "comment": song.get("comment") or "",
        "language": song.get("language") or "",
        "lyrics": song.get("lyrics") or "",
        "albumMbId": album.get("mbid") or "",
        "artistMbId": artist.get("mbid") or "",
        "albumArtistMbId": albumArtist.get("mbid") or "",
        "averageRating": float(song.get("averagerating") or 0),
        "preciseRating": float(song.get("preciserating") or 0),
        "rating": float(song.get("rating") or 0),
        "multiUserId": "",
        "searchTitle": _searchTitle(title),
    }


def _searchTitle(title: str) -> str:
    # Same normalization as ArtistMapper._searchName (observed in real rows).
    return " ".join(title.replace("(", "").replace(")", "").split())
