# ampachedata

**Client library for the Ampache JSON API with a SQLite write-through data layer.**

Every API response is persisted to SQLite first, then read back - the database is
the single source of truth, and callers never receive raw server payloads.
Zero runtime dependencies, stdlib only (pure Python + `sqlite3`).

- Live-proven against real Ampache 8.x, 7.x servers
- Session persistence across process restarts, with silent re-auth + one retry on expiry
- Two layers: `AmpacheClient` for network + write-through, repositories for offline reads (no network)
- Cleartext passwords are accepted once, hashed in memory, and never stored or logged

## Requirements

- Python **3.11+**
- An existing SQLite database with the schema (see below - the library never
  creates or alters schema, by design)

## Installation

```bash
pip install ampachedata
```

Optional dev extras (pytest):

```bash
pip install ampachedata[dev]
```

From source:

```bash
git clone https://github.com/icefields/Ampache-Data-Library
cd Ampache-Data-Library
pip install -e .
```

## Quick start

**1. Create the database** (one time). The library deliberately never creates
schema - you own the file. Build it from the repository's schema:

```python
import sqlite3

conn = sqlite3.connect("musicdb.db")
conn.executescript(open("docs/schema.sql", encoding="utf-8").read())
conn.close()
```

(`docs/schema.sql` lives in the
[repository](https://github.com/icefields/Ampache-Data-Library/blob/main/docs/schema.sql) -
it is not shipped inside the package.)

**2. Store credentials** (one time per user/server). The cleartext password is
accepted once, hashed with SHA256 in memory, and only the digest is persisted:

```python
from ampachedata import storeCredentialsFromPassword

storeCredentialsFromPassword(
    dbPath="musicdb.db",
    username="alice",
    serverUrl="https://ampache.example.com",
    cleartextPassword="secret",
)
```

Or use the CLI (hidden prompt, stdin, or env var - no `--password` flag, so
cleartext never lands in argv or shell history):

```bash
python -m ampachedata init-credentials --db-path musicdb.db
# or fully scripted:
python -m ampachedata init-credentials --db-path musicdb.db \
    --username alice --server-url https://ampache.example.com --password-stdin
```

If you already hold a pre-hashed Ampache API key (64 lowercase hex chars), use
`storeCredentialsFromKey` or the `--key-stdin` / `--key` flags instead.

**3. Use the client.** The first authenticated call triggers the handshake
from the stored credentials automatically - no explicit login step:

```python
from ampachedata import AmpacheClient

client = AmpacheClient(dbPath="musicdb.db")

artists = client.getArtists(limit=50)
print(artists[0].name)

# Write-through: everything fetched is already in the DB
songs = client.getSongs(filter="Supernaut", exact=1)

# Build a playable URL (no network call, nothing persisted)
url = client.getStreamUrl(songs[0].id, stats=0)

# Done for this session - tears down the server session cleanly
client.goodbye()
```

## Architecture: write-through, both directions

```
                ┌───────────────────────────────┐
   Ampache ────▶│  AmpacheClient (network layer) │────▶ SQLite (musicdb.db)
   JSON API     │  persist first, read back     │           │
                └───────────────────────────────┘           ▼
                ┌───────────────────────────────┐
   Your UI ◀───│  Repositories (offline layer)  │◀─── typed entities
   (no network) │  list / search / count / page  │
                └───────────────────────────────┘
```

- **Network layer** (`AmpacheClient`): every library-data fetch persists the
  response to SQLite *first*, then returns typed entities read back from the
  database - never raw JSON. (The media-URL builders are pure string builders:
  no network, no DB write. `ping` without a stored session is an anonymous
  probe that persists nothing.)
- **Offline layer** (repositories): query what has been cached. Zero network.
  Built for UI list views, search boxes, and pagination.

Consequence: offline reads only see what has been fetched at least once. Start
from an empty DB and `listSongs()` returns nothing until you fetch. This is the
intended cold-cache model, not a bug.

## AmpacheClient reference

Constructed as `AmpacheClient(dbPath, transport=None)` - `transport` is
an optional HTTP transport injection seam (used by the test suite; the
default is a stdlib urllib transport).

All list methods auto-paginate server-side (loop until short page) - you never
page by hand. Entity ids are strings throughout; returned entities are
immutable frozen dataclasses with clean field names (no JSON keys, no DB-only
columns).

> **Unfiltered list calls sync everything.** `getSongs()` with no `filter` and
> no `limit` fetches the *entire server library* into your DB in one call
> (same for `getArtists()`, `getAlbums()`, …). That is the intended
> write-through sync behavior - but be deliberate about it.

### Session & health

| Method | Returns | Notes |
|---|---|---|
| `ping()` | `PingResult` | Health check: `authenticated`, `api`, `server`, `version`, `sessionExpire`. Some servers answer `authenticated` optimistically - don't rely on ping as a session probe. |
| `goodbye()` | `OperationResult` | Tears down the server session and deletes the persisted token. After goodbye, **authenticated calls raise `InvalidHandshakeError`** (no resurrection on this instance) - but `ping()` falls back to anonymous mode and returns `authenticated=False`. Create a new `AmpacheClient` to re-auth. |
| `lastPayload` (property) | `dict` or `None` | The raw envelope of the last call (informational: `total_count`, `md5`, …). |

Sessions persist across restarts and process kills (the token lives in the DB).
On expiry (error 4701 / HTTP 401/403), the client silently re-authenticates
and retries **once**; a second failure raises `InvalidHandshakeError`.

### Artists

| Method | Returns |
|---|---|
| `getArtists(filter="", exact=None, add=None, update=None, include=None, albumArtist=None, offset=None, limit=None, cond=None, sort=None)` | `list[Artist]` |
| `getArtist(filter, include=None)` | `Artist` - `include="albums,songs"` upserts nested rows |

### Albums

| Method | Returns |
|---|---|
| `getAlbums(filter="", exact=None, offset=None, limit=None, add=None, update=None, cond=None, sort=None)` | `list[Album]` |
| `getAlbum(filter, include=None)` | `Album` |
| `getAlbumsFromArtist(artistId, albumArtist=None, offset=None, limit=None, cond=None, sort=None)` | `list[Album]` |
| `getAlbumSongs(albumId, offset=None, limit=None, cond=None, sort=None)` | `list[Song]` |

### Songs

| Method | Returns |
|---|---|
| `getSongs(filter="", exact=None, add=None, update=None, offset=None, limit=None, cond=None, sort=None)` | `list[Song]` |
| `getSong(filter)` | `Song` |
| `getArtistSongs(artistId, top50=None, offset=None, limit=None, cond=None, sort=None)` | `list[Song]` |

> `cond` and `sort` are **string** parameters, passed through to the server
> verbatim (`cond` is a `;`-separated filter string per the Ampache API;
> anything you pass is stringified into the query - build the string
> yourself). Power-user parameters; everything else is the common case.

### Stats (play-derived)

All take `(userId=None, username=None, offset=None, limit=None)`.

| Songs | Albums |
|---|---|
| `getRecentSongs()` | `getRecentAlbums()` |
| `getFrequentSongs()` | `getFrequentAlbums()` |
| `getForgottenSongs()` | `getForgottenAlbums()` |
| `getRandomSongs()` | `getRandomAlbums()` |
| `getNewestSongs()` | `getNewestAlbums()` |
| `getHighestSongs()` | `getHighestAlbums()` |

### Playlists

| Method | Returns |
|---|---|
| `getPlaylists(filter="", hideSearch=None, showDupes=None, exact=None, add=None, update=None, offset=None, limit=None, cond=None, sort=None)` | `list[Playlist]` |
| `getPlaylist(filter)` | `Playlist` |
| `getSongsFromPlaylist(playlistId, random=None, offset=None, limit=None)` | `list[Song]` - order matches the server's playlist positions exactly (no renumbering) |

### Media URLs

| Method | Returns | Notes |
|---|---|---|
| `getStreamUrl(songId, format=None, bitrate=None, offset=None, stats=None)` | `str` | Pure URL builder: no network, no DB write. Song-only per API spec. |
| `getDownloadUrl(songId, format=None, bitrate=None, stats=None)` | `str` | Same - download flavor. |

The URLs embed the live session token **as a query parameter** - treat them
as secrets: don't log them, share them, or paste them into bug reports.
The library never logs or stores built URLs. Pass `stats=0` for any fetch that is not
a real user play (preloading, probing, artwork) - otherwise the server records a
play and pollutes play counts.

### Interactions (mutate server state)

| Method | Returns | Notes |
|---|---|---|
| `flag(objectType, objectId, flagged)` | the re-fetched, refreshed entity | Applies, re-fetches via the type's getter, upserts, verifies - raises `CacheVerificationError` on mismatch. |
| `rate(objectType, objectId, rating)` | the re-fetched, refreshed entity | `rating` validated locally as 0–5 **before any network call - out of range raises plain `ValueError`**, not an `AmpacheError`. Same verify discipline. |

`objectType` accepts an `ObjectType` enum member or its plain string value
(`"song"`, `"album"`, `"artist"`, `"playlist"`).

## Offline query tier

Import `Database` plus the repositories and read what's cached - no network,
no handshake needed:

```python
from ampachedata import Database, SongRepository, ArtistRepository

db = Database("musicdb.db")
songs = SongRepository(db)
artists = ArtistRepository(db)

page = songs.listSongs(order="recent", limit=100, offset=0)
print(len(page.rows), "of", page.total)      # total = honest SQL COUNT

hits = songs.searchSongs("Supernaut")         # LIKE search, % and _ are
                                              # escaped - input is literal
byName = artists.searchArtists("megadeth")    # case-insensitive (ASCII)
```

`PageResult` carries `rows` and `total`; `total` is the SQL COUNT over the full
filtered set - unlike server envelopes, it never lies, so you can compute page
counts reliably.

| Repository | Read methods |
|---|---|
| `SongRepository` | `listSongs(order, limit, offset, artistId, albumId)`, `searchSongs(query, limit, offset)`, `songCount()`, `playlistSongs(playlistId)` (position order; `getPlaylistSongs()` is an alias), `getSong(songId)`, `getAlbumSongs(albumId)`, `getArtistSongs(artistId)`, `getSongsByLastPlayed(ascending=False)`, `getSongsByPlayCount()`, `getSongs()` |
| `ArtistRepository` | `listArtists()`, `searchArtists(query)`, `artistCount()`, `getArtist(artistId)`, `getArtists()` |
| `AlbumRepository` | `listAlbums()`, `searchAlbums(query)`, `albumCount()`, `getAlbum(albumId)`, `getAlbumsFromArtist(artistId)`, `getAlbums()` |
| `PlaylistRepository` | `listPlaylists()`, `searchPlaylists(query)`, `playlistCount()`, `getPlaylist(playlistId)`, `getPlaylists()` |

`order` for `listSongs` is one of `"title"`, `"artist"`, `"album"`, `"recent"`
(whitelisted - arbitrary SQL cannot be injected).

Case-insensitive search is ASCII-only (e.g. Cyrillic matches case-sensitively) -
that is SQLite `LIKE` semantics, documented rather than worked around.

## Errors

Every exception derives from `AmpacheError`. Catch the family, or the exact
class:

```
AmpacheError
├── DatabaseError                # musicdb.db missing or unusable
├── CredentialValidationError    # bootstrap input failed validation
├── CacheVerificationError       # post-flag/rate read-back mismatch
└── ApiError                     # Ampache error envelope
    ├── InvalidHandshakeError     # 4701 / HTTP 401/403 - triggers auto re-auth (except after goodbye)
    ├── AccessDeniedError         # 4703
    ├── NotFoundError             # 4704
    ├── DeprecatedError           # 4706
    ├── BadRequestError           # 4710
    └── UnknownApiError           # anything else
```

`ApiError` carries `.code` and `.message`. Error messages never contain the
cleartext password or the stored hash.

## Best practices

- **Let the library own writes.** All upserts (history, playlist positions,
  ratings) derive from server payloads - never write entity rows by hand.
- **Don't trust server `total_count` envelopes** - some Ampache builds report
  stale/wrong counts. The client auto-paginates until a short page; for offline
  paging use `PageResult.total` instead.
- **Pass `stats=0` on non-playback media fetches** so plays aren't recorded.
- **Treat built stream/download URLs as secrets** - they embed the live
  session token as a query parameter.
- **Call `goodbye()` when done** - it's the clean logout, and it deletes the
  stored session token. Reuse one client per session rather than one per call.
- **Create the client fresh after `goodbye()`** - a post-goodbye client raises
  `InvalidHandshakeError` by design (no resurrection).
- **Exact filters with special characters** (`?`, `%`, `_`) can behave
  inconsistently on some servers; prefer narrow, plain-text filters.
- **Songs removed from a playlist stay in the cache** - playlist join rows are
  upsert-only (no deletion), so offline reads keep showing them until the
  server's next payload omits them.
- **Not thread-safe** - the client holds one SQLite connection (sqlite3's
  default `check_same_thread` behavior); using one client instance across
  threads raises. Create one client per thread.
- **Keep the DB per-user** - history rows are keyed by user + media id.

## Server compatibility

Developed and live-tested against **Ampache 8.0.x** (`json.server.php`, JSON
API). The method set (handshake, ping, artists/albums/songs, stats,
playlists, flag, rate, stream, download, goodbye) is long-standing Ampache
JSON API surface, but only 8.0.x has been live-proven. Python 3.11–3.14
supported.

## License

[GPL-3.0-only](LICENSE) - the full license text ships in the sdist and wheel.

## Links

- Source & issues: <https://github.com/icefields/Ampache-Data-Library>
- PyPI: <https://pypi.org/project/ampachedata/>
