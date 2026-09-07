# PowerAmpacheData

Importable Python library for the Ampache JSON API (api6/api8) with a
SQLite write-through data layer. The DB is the single source of truth:
every API response is persisted first, then read back — never returned raw.

## Layout

```
src/ampachedata/              the installable package (pip install -e .)
  domain/                     entities + result types (no I/O)
  data/                       HTTP, auth, mappers, repositories
pyproject.toml                src layout, zero runtime deps
docs/
  ampache-api-json-methods.md read-only API spec
  schema.sql                  musicdb.db schema (read-only)
  examples/                   real server responses (read-only)
tests/                        unit tests (fake transport, example fixtures)
musicdb.db                    Room schema DB — never created or ALTERed
CONVENTIONS.md                project rules — binding, read before coding
aider-ampache-tutorial.md     build walkthrough (start here)
```

## Install

```
pip install -e .
```

Then `import ampachedata` from any project. Configuration is injected:
`AmpacheClient(dbPath=...)` — the DB path belongs to the caller.

## Rules

CONVENTIONS.md is binding. `docs/` is read-only reference material.
No pushes without explicit approval.