# Changelog

## Unreleased — distribution

- Prepared for PyPI + the official MCP Registry. Renamed the distributable to `mcp-applemusic-nodesaint` (upstream owns `mcp-applemusic` on PyPI); console script renamed to match so `uvx mcp-applemusic-nodesaint` works. Added PyPI metadata (license, keywords, classifiers, URLs).
- Added `server.json` (registry manifest, `io.github.nodesaint/mcp-applemusic`) and the `<!-- mcp-name: … -->` ownership marker in the README.
- Added `PUBLISHING.md` with the exact PyPI + `mcp-publisher` steps.
- Set the GitHub repo description and MCP discovery topics so directories (Glama, PulseMCP, mcp.so) can index it.
- README install commands updated to the PyPI package.

## 0.2.3 — 2026-07-05 — safe-by-choice controls

OWASP Top 10 pass. Most items are N/A (no network, DB, auth, or web input in the server); the two that apply:

- **A06 (vulnerable components):** ran `pip-audit` on the full dependency tree — no known vulnerabilities.
- **A01 / A04 (access control & insecure design):** added `MUSIC_MCP_READONLY`. When set, every state-changing tool (playback, set_options, play, rate, and all playlist create/add/remove/rename/delete) is refused before it runs, leaving only search/browse. This is the hard stop against a prompt-injected model deleting or overwriting a playlist. Default (unset) keeps full functionality. 4 new tests; verified live that writes are blocked and reads still work.

## 0.2.2 — 2026-07-05 — second security pass

Thorough review of the whole package. Verified clean: single osascript gateway (no other subprocess/`eval`/`exec`), no network surface, no secrets, `--` terminator in place, all values via argv.

Two findings fixed:

- **Output field-injection via crafted metadata (low severity, defense-in-depth).** Track/playlist names are influenceable by whoever publishes a track; a name containing a raw US/RS delimiter control character could inject an extra field or a phantom record into the parsed output the model sees. Added a shared AppleScript `san()` handler that strips those control characters from every emitted free-text field (name, artist, album, genre, playlist name). Persistent IDs were already injection-proof (system-generated, always first).
- **PATH-lookup surface.** `osascript` was invoked by bare name. Pinned to the absolute system path `/usr/bin/osascript`.

## Unreleased (branch: dev)

- Rewrote `README.md` — proper hero, quick example, categorized tool tables, security and roadmap sections.
- Added a 3D landing page (`site/index.html`) deployed to GitHub Pages at https://nodesaint.github.io/mcp-applemusic/ from the `gh-pages` branch. Three.js hero (rotating vinyl record + audio-waveform particle field with bloom), Apple Music gradient aesthetic, Fontshare/Clash Display type, scroll reveals, custom cursor, graceful CSS fallback if WebGL/CDN is unavailable.

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
