# CONVENTIONS.md — Ampache Client Library

Read this before writing any code. These rules override Aider's defaults.

## Project Goal

A clean, reusable client library for the Ampache JSON API (api6/api8 methods).
The full API spec lives in `ampache-api-json-methods.md` (read-only reference).
Ground-truth response shapes live in `examples/*.json` — when code and docs
disagree, the examples win.

## Language & Naming

- **Naming (Java convention, applies in every language):**
  - functions/methods/variables: `lowerCamelCase`
  - classes/types: `PascalCase`
  - constants: `ALL_CAPS_SNAKE`
  - files: one primary class per file, named after it (`AmpacheClient.py`, `Handshake.py`)
- No magic strings — API method names, error codes, and object types live in
  enums/constants near the top of the layer that owns them.
- Prefer composition over inheritance. No god classes.

## Architecture — three layers, one-way dependencies

```
domain/        ← entities + result types (Song, Album, Artist, Playlist, ...)
                 no I/O, no HTTP, no JSON parsing knowledge
data/          ← AmpacheClient (HTTP transport, auth/session, request building)
                 + response mappers (raw JSON → DB rows)
                 + repositories (DB reads → domain entities)
presentation/  ← optional facade / CLI / display code. Calls domain or data,
                 never raw HTTP.
```

Rules:
- `domain/` imports nothing from `data/` or `presentation/`. Ever.
- `data/` may import `domain/`. `presentation/` may import both.
- JSON keys appear ONLY in `data/` mappers. Domain entities use clean names.
- One mapper per response object type (song, album, artist, playlist, genre,
  catalog...). The object schema tables at the end of
  `ampache-api-json-methods.md` define the fields.

## Packaging — an importable library, not a script collection

This project's output is a library any Python project can import. That
shapes the tree from day one:

- The whole tree is one installable package under `src/ampachedata/`,
  with `__init__.py` re-exporting ONLY the public API (the client facade,
  domain entities, result types, exceptions). Anything not re-exported is
  private — internals may be renamed or moved freely.
- `pyproject.toml` at repo root: src layout, setuptools, zero third-party
  runtime dependencies — stdlib only (sqlite3, hashlib, json, urllib).
  Dev/test deps (e.g. pytest) live in the optional `dev` extra.
- Consumers install with `pip install -e .` and `import ampachedata`.
  Tests import the installed package — no `sys.path.insert` hacks, ever.
- Configuration is injected, never hardcoded: `AmpacheClient(dbPath=...)`.
  The DB path — like the credentials inside it — belongs to the caller.
  `serverUrl` still comes from `CredentialsEntity` in the DB.

## Auth & Session (the tricky part — get this right)

- **The DB is the auth store.** `SessionEntity` holds a single row (PK
  `primaryKey`): the current session token (`auth`), `sessionExpire`, api
  version and catalog counts — used for auto-authentication on every API
  call. `CredentialsEntity` holds a single row: `username`, `password`,
  `authToken` (API key mode), `serverUrl` — everything needed to re-auth.
  Nothing auth-related is kept only in memory or in code.
- **`CredentialsEntity.password` stores the password HASH — never the
  cleartext.** Verified against the existing row: 64 lowercase hex chars =
  `SHA256(password)` — that's the "KEY" in Ampache's handshake docs. (Not
  MD5, not cleartext.) The handshake passphrase is
  `SHA256(timestamp + <stored hash>)`, so re-auth needs ONLY what's in the
  DB. The cleartext password must never be stored, logged, or requested
  again. If setup ever receives a cleartext password: hash it immediately,
  persist only the digest, discard the original.
- `SessionEntity.auth` is the **session token** returned by the handshake
  (32-char hex) — NOT the password hash. Two different values in two
  different tables; never mix them up.
- Handshake: `auth = SHA256(timestamp + SHA256(password))` sent with
  `user=<username>` (credentials from `CredentialsEntity`). NOT the raw
  password, NOT the stored token.
- The handshake response returns `auth` (session token) + session expiry —
  persist both to the `SessionEntity` row (upsert, never insert a second row).
- **Token expiry: never logout.** The token is time-limited; when it expires
  (or error 4701 comes back), silently fetch a new one via handshake using
  the credentials already in the DB, update the `SessionEntity` row, and
  retry the original call. `goodbye`/logout is NOT part of the re-auth flow.
- Also support API-key auth (`authToken` in `CredentialsEntity`; per docs
  the passphrase is `SHA256(user + SHA256(apikey))` — re-verify against the
  spec before implementing).
- **Send the session token via `Authorization: Bearer` header or request
  body — never the query string.** Query-string `auth` is deprecated in the
  spec (privacy: URLs get logged everywhere).
- `ping` doubles as the health check / expiry probe.
- Credentials NEVER in code or committed files. The DB is their home.

## Request Building

- Endpoint pattern: `GET/POST {server}/server/json.server.php?action=<method>&...`
- Parameters: query string for GET; form-encoded or JSON body for
  POST/PUT/PATCH/DELETE (spec allows both — pick form-encoded, document it).
- All list methods accept `filter`, `exact`, `offset`, `limit` — implement
  pagination once (in `data/`), reuse everywhere. Default/maximum `limit`
  handling belongs in one place.
- `include=1` toggles nested objects — mapper must handle both shapes.
- Write methods (bookmark_*, playlist_*, collection_*, catalog_*) return
  success/error envelopes, not entities — model them as result types, not
  half-parsed objects.

## Persistence — SQLite is the Single Source of Truth (write-through)

**Non-negotiable pattern. Every read method follows it.**

```lua
function getAlbum(id)
    local apiResp = api.getAlbum(id)
    insertIntoDB(apiResp)
    return db.getAlbum(id)
end
```

- The SQLite database (`musicdb.db`) is provided up front. **Never invent or
  ALTER tables.** For response fields with no column: apply the aliases and
  ignore-list in the Field Mapping section below — do not stop to ask unless
  a field is in neither list.
- Every API response is written to the DB **first**; the return value comes
  **only** from querying the DB afterward. Never return the parsed response
  directly. We knowingly pay a small performance price for consistency.
- Upsert semantics: INSERT OR REPLACE keyed on each table's actual primary
  key (see the PK list below) so repeated calls refresh, never duplicate.
- Nested objects are normalized: an album response containing its artist
  writes both the album row and the artist row (same rules, recursively),
  referencing by id — not flattened JSON blobs in a column.
- List responses are one transaction: all rows written + committed before
  the read-back query runs. No partial writes on failure.
- Write methods (bookmark_*, playlist_*, ...) still return result types as
  per the Error Handling section — but any entity data they carry is also
  persisted the same way.
- DB access lives in `data/` repositories. `domain/` and `presentation/`
  never touch SQL.
- **The DB (`musicdb.db`) is a Room (Android) schema — tables already exist.
  Map directly onto them; never invent or ALTER.** Out of scope:
  `DownloadedSongEntity` (ignore entirely), `LocalSettingsEntity`,
  `room_master_table`, `android_metadata`, `RecommendedArtistEntity`.
  The `MultiUser*` tables and the `multiUserId` column exist for multi-user
  mode — library runs single-user; write the default `''`, read without
  filtering, and leave multi-user for later.
- **Primary keys are not uniform — get these right:**
  - `SongEntity` → `mediaId` (NOT `id`; the API `id` goes into `mediaId`)
  - `AlbumEntity`, `ArtistEntity`, `GenreEntity`, `PlaylistEntity`,
    `UserEntity` → `id`
  - `PlaylistSongEntity` → `id` (its own row id), carries `songId`,
    `playlistId`, `position` — playlist ordering lives here
  - `HistoryEntity` → `id`, carries `mediaId`, `playCount`, `lastPlayed`
  - `SessionEntity`, `CredentialsEntity` → `primaryKey`, **single row each**
- Upserts: `INSERT OR REPLACE` keyed on the table's actual PK — **only for
  full objects** (complete response payloads). For partial references (a bare
  `{id, name}` NamedReference nested inside another object) NEVER
  `INSERT OR REPLACE` — it would blank out every real column. Either skip
  writing the referenced row, or `INSERT ... ON CONFLICT(id) DO UPDATE` the
  name fields only.
- **Array-ish response fields (genre, artists, artUrl with multiple sizes,
  ...) are TEXT columns holding the response's own JSON fragment verbatim**
  (e.g. `{"attr":[{"id":"4","name":"Metal"}]}`), matching the existing
  rows' format. No re-serialization, no flattening — copy the fragment as-is.
  Reading those fields back is the consumer's concern, not the mapper's.
- **List ordering is DB-derived:** play history → `HistoryEntity`
  (`lastPlayed`), playlist order → `PlaylistSongEntity.position`. If some
  future method's ordering can't be represented, flag it and ask — a targeted
  "persist history, read back from response" exception is allowed but must
  be explicit, never improvised.

## Field Mapping — verified against `musicdb.db` columns

Diffed: real response fields (from `examples/*.json`) vs actual table
  columns. A field is either aliased, stored elsewhere in the schema, or
  **dropped** (documented, silent). No other options; never invent columns.

### Aliases (different name, same destination)
- song `id` → `SongEntity.mediaId`; song `url` → `songUrl`
- playlist `user` → `owner`
- `has_art` / `art` object → `artUrl` / `imageUrl` (URL extracted; boolean
  implied by non-empty value)
- song `last_played` (ISO 8601 string) → `HistoryEntity.lastPlayed`
  (epoch **milliseconds** — verified against existing rows) and
  `play_count` → `HistoryEntity.playCount`; the mapper converts
- album `mbid` → not stored on the album row; per-song `albumMbId` lives on
  `SongEntity`

### Dropped (no column — silently ignore, by design)
- **Song:** `license`, `replaygain_album_gain`, `replaygain_album_peak`,
  `r128_album_gain`, `r128_track_gain` (track replaygain IS stored)
- **Album:** `prefix`, `songartists`, `tracks`, `type`, `mbid`, `mbid_group`,
  `catalog`, `has_art` (aliased)
- **Artist:** `prefix`, `basename`, `rating`, `averagerating`, `mbid`
- **Playlist:** `has_access`, `has_collaborate`, `md5`, `last_update`, `time`
- **Genre:** `videos`, `live_streams`, `is_hidden`, `merge`
- **User:** `auth`, `validation`, `link`, `has_art`

This list is final. If a NEW unmapped field appears (API version change),
add it to the drop list with a comment — don't ask, don't invent columns.

## Error Handling

Map every documented error code to a typed exception/result — the codes are
in the spec's intro section (4710 BAD_REQUEST, 4701 INVALID_HANDSHAKE, 4703
ACCESS_DENIED, 4704 NOT_FOUND, 4706 DEPRECATED, ...). One exception hierarchy
in `data/`, translated to domain-level failures at the boundary if needed.
Never let raw HTTP status codes leak past `data/`.

Binary/streaming methods (media) return raw bytes/stream handles, not JSON.

## Testing

- Response mappers are tested against files in `examples/` (they're real
  server responses — load the JSON, map it, assert fields).
- HTTP layer gets a fake transport (inject the HTTP client / session sender)
  — no live server in unit tests.
- Auth test: verify SHA256 composition against a known-good vector.

## Aider Ground Rules

- `ampache-api-json-methods.md` and `examples/` are READ-ONLY reference
  material. Never edit, never "fix", never reformat them.
- Never invent API fields or methods. If the spec/examples don't show it,
  ask instead of guessing.
- When adding a method: read its section in the spec md, read its example
  json (if present), write mapper + tests in the same change.
- Keep diffs scoped: one API method or one layer concern per commit.
- No new dependencies without asking first. Stdlib preferred.

## Git Safety

- `.gitignore` contains `.env*`, `*_state.json`, `examples/` (if repo-local
  copy), credentials — BEFORE first commit.
- No push without explicit approval. Ever.