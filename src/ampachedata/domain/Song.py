"""Song domain entity. Clean names — no JSON keys, no DB-only columns
(multiUserId, searchTitle, flag stay in the DB layer). Nullable response
fields the mapper passes through untouched (mime, mode, publisher, the
replaygain pair, ...) keep their nullability."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Song:
    id: str                     # SongEntity.mediaId — the API id lands there
    title: str
    albumId: str
    albumName: str
    artistId: str
    artistName: str
    albumArtist: str
    songUrl: str
    imageUrl: str
    bitrate: int
    streamBitrate: int
    catalog: int
    channels: int
    composer: str
    filename: str
    genre: str                  # response's own JSON fragment, verbatim
    mime: Optional[str]
    playCount: int
    playlistTrackNumber: int
    rateHz: int
    size: int
    time: int
    trackNumber: int
    year: int
    name: str
    mode: Optional[str]
    artists: str                # response's own JSON fragment, verbatim
    streamFormat: Optional[str]
    format: Optional[str]
    streamMime: Optional[str]
    publisher: Optional[str]
    replayGainTrackGain: Optional[float]
    replayGainTrackPeak: Optional[float]
    disk: int
    diskSubtitle: str
    mbId: str
    comment: str
    language: str
    lyrics: str
    albumMbId: str
    artistMbId: str
    albumArtistMbId: str
    averageRating: float
    preciseRating: float
    rating: float
