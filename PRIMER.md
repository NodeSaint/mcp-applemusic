# PRIMER

Session continuity notes. Update before context is lost.

## Current state (2026-07-05)

**Phase 1 (AppleScript-deep) is COMPLETE, live-verified, and MERGED TO `main` (v0.2.1).** Fork of kennethreitz/mcp-applemusic at NodeSaint/mcp-applemusic. `main` = released/installable version; `dev` = ongoing work; `gh-pages` = landing page. The README install command (`uvx --from git+…/mcp-applemusic`) pulls `main`, so main must always stay installable. Verified end-to-end: `uvx` from the default branch builds, installs, and boots clean.

- 14 `music_*` tools (playback, search, ratings, playlist CRUD) — see README table.
- 37 unit tests pass (`uv run pytest`); live smoke passes end-to-end (`uv run python scripts/live_smoke.py`, all ops 150–850ms on the 2,804-track library).
- Architecture: `mcp_applemusic/runner.py` is the ONLY osascript caller; values go via argv (`on run argv`), never interpolated. Track identity = persistent IDs. Output = US (`\x1f`) / RS (`\x1e`) delimited records parsed in `models.py`.
- Spec: `docs/superpowers/specs/2026-07-05-hybrid-apple-music-mcp-design.md`. Plan (with critique log): `docs/superpowers/plans/2026-07-05-phase1-applescript-deep.md`.

## Distribution (prepped, awaiting user action)

- Renamed distributable to **`mcp-applemusic-nodesaint`** (upstream owns `mcp-applemusic` on PyPI). Console script renamed to match. `server.json` (registry manifest, `io.github.nodesaint/mcp-applemusic`) + `<!-- mcp-name -->` marker in README are in place. Full steps in `PUBLISHING.md`.
- **User must run** (needs their accounts, can't be automated): (1) `uv build && uv publish` to PyPI; (2) `mcp-publisher login github && mcp-publisher publish`. Until then the tool installs only from git.
- On each release, bump version in BOTH `pyproject.toml` and `server.json` (name + packages[0].version), or the registry rejects it.

## Taste layer (design scoped, not built)

- The strategic moat. Design: `docs/superpowers/specs/2026-07-05-taste-layer-design.md`. LLM does semantics (brief→intent), an engine does grounding + sequencing (flow). Verified live: Music.app exposes behavioural signal (play/skip count, rating, favorited) but **BPM returns 0 for cloud tracks and ISRC is NOT exposed** — so acoustic enrichment (Tier 1) needs fuzzy title+artist matching or Phase 2's Apple API for ISRC. v1 (taste profile + genre/behaviour sequencing) ships with no new API.

## Hard-won AppleScript gotchas (do not rediscover)

- Variable names `st` (stone unit) and `removed` (Music dictionary constant) are RESERVED — cause syntax/runtime errors inside `tell application "Music"` blocks. Verified `m, q, t, d, p, n, v, r, us, rs` are safe.
- Deleting an empty `whose` specifier does NOT error — count matches before delete or removal reporting lies.
- Use `exists user playlist X` rather than try/on-error-create, or you make duplicate playlists.
- Music's native `search <playlist> for <q> only <songs|artists|albums|all>` is fast; `whose` scans are O(n) — only used for genre.
- User's Mac: Sync Library is ON (cloud status "subscription" tracks visible). macOS 26.3, Music.app 1.6.3.

## Phase 2 (NOT started — needs user action first)

Apple Music Web API layer for full-catalog search + adding catalog songs (the "songs I don't own yet" use case). Blocked on: user buying Apple Developer membership ($99/yr) → creating a MusicKit key (.p8). Then build per spec: `api/` package (auth: ES256 dev JWT + Music User Token; catalog; library; playlists), `setup_flow/` localhost MusicKit JS token capture, dual routing in `server.py` (API preferred for create/add when configured). Also backlog: recently_added/recently_played (vectorized date fetch + Python sort), reorder_playlist (verify AppleScript `move` first).

## Conventions

- Commits authored as NodeSaint only, NO Claude co-author lines (user's global CLAUDE.md).
- Branch flow: feature/* → dev → main (main only when stable).
- Log every push in CHANGELOG.md.
