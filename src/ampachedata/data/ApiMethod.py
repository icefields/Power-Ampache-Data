"""API method names — no magic strings outside this enum."""
from enum import Enum


class ApiMethod(str, Enum):
    HANDSHAKE = "handshake"
    PING = "ping"
    ARTISTS = "artists"
    ARTIST = "artist"
    ARTIST_ALBUMS = "artist_albums"
    ALBUMS = "albums"
    ALBUM = "album"
    SONGS = "songs"
    SONG = "song"
