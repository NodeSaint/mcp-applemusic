# Changelog

## 0.2.1 — 2026-07-05 (branch: dev) — security hardening

- **Fixed an argument-injection vulnerability (high severity).** `run_script` built the `osascript` command without a `--` option terminator, so any user-controlled value beginning with `-` (e.g. `-e <script>`) was parsed by osascript as an option rather than argv data — smuggling a second script and reaching `do shell script` (arbitrary code execution). Added the `--` terminator; all user values are now unconditionally treated as data. Regression test added.
- Hardened `.gitignore` to exclude `.env`, `*.p8`, `config.json`, and secret directories ahead of the Phase 2 API layer.
- Bumped `mcp` floor `>=1.2.1` → `>=1.28.1` (latest stable) and relocked.

## 0.2.0 — 2026-07-05 (branch: dev)

Complete restructure of the upstream single-file experiment into a production server.

- **Security:** all AppleScript now executes via a single runner that passes user values as `argv` arguments — string interpolation into script source (injection vector) eliminated.
- **Reliability:** all track/playlist operations use Music.app persistent IDs instead of exact-name matching; batch operations report `missing` IDs instead of silently dropping them.
- **Tool surface:** 9 fragile tools → 14 robust ones covering playback, options (volume/shuffle/repeat), library search (field-scoped, uses Music's native fast `search` verb), track metadata, ratings/favorites, and full playlist CRUD (create, add, remove, rename, delete).
- **DJ mode:** `music_play` with `track_ids` builds and plays a "Claude Queue" playlist — album playback and ad-hoc sets without Up Next access.
- **Errors:** typed `{error, hint}` responses with actionable hints (app not running, automation permission, item not found, timeout).
- **Tests:** 37 unit tests (no Music.app required) + live smoke script exercising the real app end to end.
- Fixed AppleScript reserved-word collisions discovered in live testing (`st` = stone unit, `removed` = Music dictionary constant).
- Fork of kennethreitz/mcp-applemusic; upstream tool names (`itunes_*`) retired.
