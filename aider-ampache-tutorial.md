# Aider × Ampache — The Field Tutorial

From zero to a working Ampache client library: handshake, ping, and your
first five read methods. Written for someone who has never used Aider.
Everything between the ``` fences is copy-paste ready.

The companion files (all in your project root unless noted):
- `CONVENTIONS.md` — the law. Aider reads it automatically every session.
- `docs/ampache-api-json-methods.md` — the API spec (read on demand)
- `docs/schema.sql` — DB schema (tables exist, never ALTER)
- `docs/examples/*.json` — 155 real server responses (test fixtures)
- `musicdb.db` — real DB copy (dev artifact, gitignored)

---

## Part 0 — What you're driving

Aider is a chat REPL that edits your repo. Key facts, so nothing surprises you:

1. **It git-commits automatically after every successful change.** You never
   type `git commit`. Every change is a checkpoint; `/undo` reverts the last
   one. It never pushes — that stays yours.
2. **Repo files vs chat files.** Files you `/add` are "in the chat": aider can
   edit them and their full content occupies context. Files merely *in the
   repo* are visible in a summary map (name + signature) and aider can read
   them on demand when it decides it needs to. `docs/` stuff should stay in
   this second category — visible, not resident.
3. **`CONVENTIONS.md` in the root is auto-loaded into every chat.** You don't
   /add it, you don't mention it. This is why we wrote it.
4. **`--continue` resumes the last session, `--resume` picks one from a list.**
   Chat logs are saved in `.aider.chat.history.md` and `.aider.input.history`.
5. **The model can read files itself.** Prompting "read the album section of
   docs/ampache-api-json-methods.md and implement it" works — aider will open
   the file. You don't need to paste specs into chat.

### Recommended `.aiderignore` (in project root)

```
musicdb.db
docs/examples/
docs/ampache-api-json-methods.md
```

Wait — didn't I say aider can read those? Yes: `.aiderignore` only keeps files
out of the *automatic repo map* (the token-costly summary). Aider can still
open them when a prompt names them. This keeps the map lean while the
prompts below explicitly point at the right file every time.

### Launch

```
aider
```

That's it — model config is already done on your box. Two useful optional
flags (put in `.aider.conf.yml` in the repo root if you like them):

```yaml
auto-test: true
test-cmd: python -m pytest -x -q
```

`--auto-test` runs the test command after every change and shows failures
straight to the model, so it self-corrects. Strongly recommended.

---

## Part 1 — Session 1: skeleton + handshake + ping

### Step 1.1 — Plan first, write never (`/ask` mode)

Start aider in the project root and paste:

```
/ask Read CONVENTIONS.md, docs/schema.sql, and docs/examples/handshake.json.
Propose the module layout for this Ampache client library:
- the file tree for src/ and tests/
- how the write-through pattern (API response → DB → read back) flows through
  your proposed classes
- one method traced end-to-end: handshake
Do not write any code yet. Do not create files.
```

`/ask` answers without touching disk. Expect a tree like:

```
src/
  ampachedata/            ← the installable package (pip install -e .)
    __init__.py           (re-exports the public API only)
    domain/
      song.py  album.py  artist.py  playlist.py  ...   (plain entities)
    data/
      http_client.py        (transport: request building, Bearer header)
      auth.py               (handshake, ping, re-auth-on-expiry)
      mappers.py → or mapper_song.py, mapper_album.py, ...
      repositories.py → or repository_song.py, ...
      db.py                 (connection, upserts, transactions)
      errors.py             (typed AmpacheError hierarchy, code→exception)
      client.py             (AmpacheClient: public methods, write-through flow)
    presentation/  (later, if ever)
pyproject.toml              (src layout, zero runtime deps)
```

Names may differ — that's fine. What must be present:
- a clear `domain`/`data` split (one-way imports only)
- one place that owns HTTP, one that owns SQL
- the write-through flow visible in the client method shape:
  fetch → mapper → upsert → repository read-back → return entity

**Argue now, not later.** If you dislike something:

```
/ask I don't like X because Y. What if we did Z instead?
```

Iterate in /ask until the plan reads right. This is cheap; fixing structure
after 20 methods exist is not.

### Step 1.2 — Build it (the "Go")

```
Implement the skeleton we just discussed:
1. `src/ampachedata/` package layout with empty modules and docstrings,
   plus a root `pyproject.toml` (src layout, zero runtime deps) per the
   Packaging section of CONVENTIONS.md.
2. Full handshake + ping per CONVENTIONS:
   - passphrase = SHA256(timestamp + SHA256(password)) — credentials come
     from CredentialsEntity (password column holds the SHA256 KEY already;
     never store or ask for cleartext)
   - single-row upsert of SessionEntity (auth, session_expire, api, counts)
   - send auth via Authorization: Bearer header, never the query string
   - ping: with session token it extends the session; without, just returns
     server/version/compatible
   - re-auth: on expired token or error 4701, silently handshake again with
     stored credentials, update the SessionEntity row, retry the original
     call ONCE. goodbye/logout is never called.
3. AmpacheError hierarchy in data/errors.py mapping the documented codes
   (4701 INVALID_HANDSHAKE, 4703 ACCESS_DENIED, 4704 NOT_FOUND, 4706
   DEPRECATED, 4710 BAD_REQUEST, ...).
4. DB bootstrap: open musicdb.db from a configurable path; schema must NOT
   be created or altered by the library.
5. Tests: fake HTTP transport (injectable) — no network. Test the auth
   composition against this known vector:
     KEY       = SHA256("demo")            = 2a97516c354b68848cdbd8f54a226a0a55b21ed138e207ad6c5cbb9c00aa5aea
     timestamp = 1700000000
     passphrase= SHA256("1700000000" + KEY) = 53ec985108e46054a949f8d5c609797690711ba0571bdef28b8226e1aa845034
   Also test handshake response → SessionEntity row against
   docs/examples/handshake.json, and re-auth-on-4701 with the fake transport
   returning 4701 once then a fresh handshake.
Add all new files to the chat as you create them.
```

Why the vector matters: SHA256 composition is the #1 thing models fumble
(trailing newlines, wrong concatenation order). A hardcoded known-answer test
makes it impossible to ship subtly-broken auth.

While it works, aider will ask, per new file: `Add file to the chat?` —
say yes (`y`). That's normal, not a problem.

### Step 1.3 — Verify

```
/test python -m pytest -x -q
```

or just `/test` if you configured test-cmd. Failures get fed to the model
automatically; watch it iterate. When green:

### Step 1.4 — Review like an adult, not a fan

```
/diff
```

then in a shell (outside aider, or `/run`):

```
git log --oneline -5
```

Check specifically:
- **SessionEntity**: exactly one row written, upsert not insert (`SELECT COUNT(*) FROM SessionEntity` against a scratch copy of the DB — never the real one in tests; tests should copy musicdb.db or build from docs/schema.sql)
- **No cleartext anywhere**: `git grep -i password` should only show the hash handling
- **Bearer header**, not `&auth=` in URLs
- **session_expire stored as the ISO string** exactly as the server sent (observed format: `2025-12-09T09:49:10`)

If something's off, don't accept it:
```
/ask Why is X like this? CONVENTIONS.md says Y.
```
then either let it fix, or `/undo` and restate.

**When the session is green, stop.** `exit` (or Ctrl-D). Optionally `git tag v0-handshake` to mark the milestone.

---

## Part 2 — Session 2: getArtists

Relaunch (fresh session = clean context = better answers): `aider --continue`
to keep this session's context, or plain `aider` for a clean slate — the
prompts below assume a CLEAN slate:

```
/clear

Implement getArtists per CONVENTIONS.md:
- API method "artists" (read its section in docs/ampache-api-json-methods.md)
- params: filter, exact, add, update, include, album_artist, offset, limit,
  cond, sort — build the query string centrally in the http client
- response envelope: {total_count, artist: [...]}; validate against
  docs/examples/artists.json
- write-through: one transaction upserting every artist row, then read back
  all of them from the DB and return the domain entities
- ArtistEntity mapping per CONVENTIONS Field Mapping section: id, name,
  albumCount/songCount from the response albumcount/songcount, genre JSON
  fragment verbatim, artUrl from art, summary, time, yearFormed, placeFormed;
  DROP the documented dropped fields (prefix, basename, rating,
  averagerating, mbid) — silently, they're in the ignore list
- searchName: normalized copy of name with parentheses stripped
  (observed in real rows: "A Beautiful Lie (Instrumental)" →
  "A Beautiful Lie Instrumental")
- the returned list is ordered by the DB read-back (ORDER BY searchName)
- multiUserId: write the default '' 
- tests first: fixture docs/examples/artists.json through the fake
  transport, upsert into a scratch DB built from docs/schema.sql, assert
  read-back fields and ordering
```

Notes on what that prompt teaches:
- It names the **API method** (`artists`) AND your **library function**
  (`getArtists`) — no ambiguity.
- "validate against docs/examples/artists.json" gives the model ground truth;
  it will read that file.
- "tests first" — say it explicitly; models write tests when told, skip them
  when not.

After it finishes: `/test`, `/diff`, review, then:

```
/ask Show me how getArtists flows from HTTP call to returned entity, and
where each CONVENTIONS.md rule is enforced.
```

That last one is a free audit. If the answer reveals a gap ("I didn't
transaction the upserts because..."), make it fix it.

---

## Part 3 — Session 3: getArtist

```
/clear

Implement getArtist(id) per CONVENTIONS.md:
- API method "artist" (read its section in docs/ampache-api-json-methods.md)
- response: single artist object; validate against docs/examples/artist.json
- CRITICAL — include handling: the response can carry nested albums[] and
  songs[] arrays (include=albums,songs). Per the Nested Objects rule, upsert
  those to AlbumEntity/SongEntity too, in the same transaction
- CRITICAL — partial reference hazard: nested NamedReference objects
  {id, name} are NOT full rows. Never INSERT OR REPLACE them into their
  tables — that blanks every real column. Upsert name fields only
  (ON CONFLICT DO UPDATE) or skip writing; the full object comes from its
  own method later
- read-back: return the ArtistEntity-mapped domain Artist, re-queried from
  the DB after the upsert
- tests: docs/examples/artist.json fixture; one test with include, one
  without; assert nested persistence happened AND that a pre-seeded
  album row kept its data when the artist response only carried a
  partial reference to it
```

The last test (pre-seeded row survives a partial write) is the one that
catches the classic INSERT OR REPLACE data-loss bug. If it fails, the model
will fix the upsert — watch it happen once and you'll never forget the
hazard.

---

## Part 4 — Session 4: getAlbumsFromArtist

```
/clear

Implement getAlbumsFromArtist(artistId) per CONVENTIONS.md:
- API method "artist_albums" (read its section in
  docs/ampache-api-json-methods.md)
- params: filter=artistId, album_artist, offset, limit, cond, sort
- response: {total_count, album: [...]}; validate against
  docs/examples/artist_albums.json
- write-through all AlbumEntity rows in one transaction
- AlbumEntity mapping per CONVENTIONS Field Mapping: id, name, artistId +
  artistName from the artist reference, artists JSON fragment verbatim,
  time, year, songCount, diskCount, genre fragment, artUrl from art,
  flag, rating, averageRating; searchName = name stripped of parentheses;
  DROP documented dropped fields (prefix, songartists, tracks, type, mbid,
  mbid_group, catalog, has_art — has_art is aliased via artUrl)
- read-back ordering: ORDER BY year, searchName (DB-derived)
- tests: fixture through fake transport, scratch DB from schema.sql,
  assert rows + ordering; include one fixture album with missing/empty
  optional fields to prove no KeyError on sparse data
```

The sparse-data test matters: real server responses have holes; mappers
must use `.get()` with defaults, not `resp["genre"]`.

---

## Part 5 — Session 5: getSongs + getSong

These two share the mapper — one session, two functions:

```
/clear

Implement getSongs and getSong per CONVENTIONS.md:
- API methods "songs" and "song" (read both sections in
  docs/ampache-api-json-methods.md)
- getSongs params: filter, exact, offset, limit, add, update, cond, sort
- getSong(id): filter=UID
- response shapes: {total_count, song: [...]} and single object; validate
  against docs/examples/songs.json and docs/examples/song.json
- SongEntity mapping per CONVENTIONS Field Mapping — the aliases:
  id → mediaId, url → songUrl, art object → imageUrl; album/artist
  references → albumId/albumName/artistId/artistName/albumArtist
  (fragment verbatim); genre fragment verbatim; searchTitle from title
- CRITICAL — play stats: song.last_played is an ISO 8601 STRING but
  HistoryEntity.lastPlayed is epoch MILLISECONDS (integer). Convert in the
  mapper. play_count → HistoryEntity.playCount. HistoryEntity row:
  id = multiUserId + mediaId (observed pattern), upsert keyed on it
- getSongs: paginated fetch (limit/offset loop until total_count reached),
  one transaction per page batch, then DB read-back ordered by searchTitle
- getSong: single fetch, upsert, read-back by mediaId
- tests: both fixtures through fake transport into scratch DB; assert
  last_played conversion (pick a known value from song.json and compute
  the expected epoch ms), assert read-back, assert pagination loop calls
  the fake transport the right number of times for a fake total_count
```

Why this session is the hardest: the song object has 47 fields, aliases,
fragment columns, and a timestamp conversion — everything the conventions
were written for. If this session goes green, the rest of the API is
repetition.

---

## Part 6 — The generalized loop (everything after these five)

Every future method is the same recipe:

1. `aider` (clean) or `/clear`
2. Prompt = the template:

```
/clear
Implement <functionName> per CONVENTIONS.md:
- API method "<ampache_action>" (read its section in
  docs/ampache-api-json-methods.md)
- params: <list from the spec section>
- response: <single object | {total_count, X: [...]} envelope>; validate
  against docs/examples/<example>.json
- write-through per conventions; map per the Field Mapping section;
  dropped fields silently per the drop list
- read-back ordered by <DB column — DB-derived ordering>
- tests first: fixture through fake transport, scratch DB from
  docs/schema.sql, assert read-back + <one method-specific edge case>
```

3. `/test`
4. `/diff` review + `/ask` free audit
5. `exit`

Method-name ↔ function mapping for your roadmap (library name → Ampache
action): getArtists → `artists`, getArtist → `artist`,
getAlbumsFromArtist → `artist_albums`, getSongs → `songs`, getSong → `song`,
getAlbums → `albums`, getAlbum → `album`, getAlbumSongs → `album_songs`,
getArtistSongs → `artist_songs`, searchSongs → `search_songs`,
getGenres → `genres`, getPlaylists → `playlists`, getPlaylist → `playlist`,
getPlaylistSongs → `playlist_songs` (playlist ordering = PlaylistSongEntity.position!),
getSimilar → `get_similar`, getFavorites → `flag` (type=song...), 
recentlyPlayed → `stats` (writes HistoryEntity ordering data naturally).

---

## Part 7 — Failure playbook (paste these when things go wrong)

**It invented a field / column:**
```
"album_mood" is not in the spec or schema.sql. CONVENTIONS.md forbids
inventing fields. Where did it come from? Remove it or justify it from
docs/ampache-api-json-methods.md.
```

**It tried to ALTER / CREATE TABLE:**
```
The schema is fixed (docs/schema.sql). Never ALTER or CREATE TABLE.
/undo and restate the change using only existing columns.
```

**It stored cleartext / asked for the password:**
```
CONVENTIONS.md Auth section: only the SHA256 key is stored, cleartext is
never stored, logged, or requested. Fix this now.
```

**Data loss after a partial reference write:**
```
The INSERT OR REPLACE wiped columns. Per CONVENTIONS, partial references
must not REPLACE full rows. Switch to ON CONFLICT DO UPDATE on name fields
only, and add a regression test with a pre-seeded row.
```

**Duplicate session rows:**
```
SessionEntity is single-row. Upsert on primaryKey, never INSERT a second
row.
```

**It's confidently wrong about the API:**
```
Don't rely on your training data for Ampache. Read the section for
<method> in docs/ampache-api-json-methods.md and the file
docs/examples/<example>.json, then redo the mapper.
```

**Half-implemented and it asks you questions mid-flight:** answer tersely
("yes", "use pytest", "searchName"). It resumes with full context.

**Answers got dumb after a long session:** `/tokens` to confirm, `/clear`,
restate the task. Context rot is real; don't fight it, flush it.

---

## Part 8 — Commands you'll actually use

- `/add <file>` — make editable (full content in chat)
- `/read <file>` — context only, cannot be edited (use for spec sections)
- `/drop <file>` / `/clear` — remove context (DO this between features)
- `/ask <q>` — question, no edits (planning, audits)
- `/test` — run tests (with auto-test: runs after every change anyway)
- `/run <cmd>` — shell, output shown to the model
- `/diff` — pending changes; `/undo` — revert last change
- `/tokens` — context budget
- `/ls` — files in chat; `/help` — everything else
- `exit` — leave. `aider --continue` — back into last session.

## Part 9 — Rules of engagement (recap)

1. One method per session. `/clear` between features.
2. `/ask` before `/go`. Argue in /ask, it's free.
3. Tests first, fixtures from docs/examples/, scratch DB from docs/schema.sql — never tests against the real musicdb.db (copy it).
4. `/diff` every time. You review the machine, not trust it.
5. Conventions violations: restate the rule + `/undo`, never debug around them.
6. Never paste credentials into chat. `.env` or the DB row only.
7. No push without you. Ever. (Aider won't; keep it that way.)

---

## Appendix — Verified facts (already encoded in CONVENTIONS.md, repeated here)

- SHA256 vector: KEY=SHA256("demo")=2a97516c...aa5aea; ts=1700000000;
  passphrase=SHA256("1700000000"+KEY)=53ec9851...45034 (no newlines when hashing)
- CredentialsEntity.password = 64-hex SHA256 key (NOT cleartext, NOT md5)
- SessionEntity.auth = 32-hex session token; single row; session_expire ISO string
- HistoryEntity.lastPlayed = epoch MILLISECONDS (e.g. 1760987489157);
  song.last_played in responses = ISO 8601 string → convert
- HistoryEntity.id pattern: multiUserId + mediaId (observed:
  "ztxmusiclyghtersru62581" = "ztxmusiclyghtersru" + "62581")
- genre/artist fragments stored verbatim as response JSON
  ({"attr":[...]} / {"id":"...","name":"..."})
- searchName/searchTitle: name with parentheses stripped
  ("A Beautiful Lie (Instrumental)" → "A Beautiful Lie Instrumental")
- auth goes in Authorization: Bearer header; query-string auth is deprecated
- ping with auth extends the session